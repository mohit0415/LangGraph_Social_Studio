"""Model selection and construction.

Two things this module does NOT do, on purpose:

1. It reads no credentials from the environment. There is no ``os.getenv`` for
   ``AZURE_OPENAI_API_KEY`` or anything like it. Every client is built from the
   credentials of the signed-in user, taken from ``configs.credentials``.
2. It has no local/Ollama tier. Both tiers are Azure; the cheap tier simply
   points at a second deployment when the user supplied one at sign-in.

Everything above that — the keyword heuristic, the pinned tasks, the prompt
cache accounting — is unchanged.
"""

import re
import threading

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_openai import AzureChatOpenAI

from configs.credentials import AzureCredentials, current_credentials
from configs.logger import get_logger

logger = get_logger(__name__)


COMPLEX_KEYWORDS = [
    "benchmark", "latency", "throughput", "architecture", "regression",
    "post-mortem", "postmortem", "incident", "root cause", "trade-off",
    "tradeoff", "migration", "study", "research", "statistically",
    "methodology", "p95", "p99", "percentile", "correlation", "hypothesis",
]

SIMPLE_KEYWORDS = [
    "launch", "announcement", "announcing", "webinar", "hiring", "meetup",
    "event", "sale", "discount", "podcast", "newsletter", "milestone",
    "partnership", "award",
]

PINNED_TASKS = frozenset({"router", "consistency", "critique"})

STRUCTURED_TASKS = PINNED_TASKS

TIERS = {
    "simple",
    "complex",
}

LONG_SOURCE_WORDS = 120


def _mentions(text: str, keywords: list[str]) -> str | None:
    for keyword in keywords:
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text):
            return keyword
    return None


def assess_with_reason(description: str) -> tuple[str, str]:
    if not description or not description.strip():
        return "simple", "no text"

    text = description.lower()

    hit = _mentions(text, COMPLEX_KEYWORDS)
    if hit:
        return "complex", f"complex keyword {hit!r}"

    hit = _mentions(text, SIMPLE_KEYWORDS)
    if hit:
        return "simple", f"simple keyword {hit!r}"

    words = len(text.split())
    if words > LONG_SOURCE_WORDS:
        return "complex", f"long source ({words} words > {LONG_SOURCE_WORDS})"

    return "simple", f"default ({words} words)"


def assess_complexity(description: str) -> str:
    return assess_with_reason(description)[0]


def resolve_tier(task: str, text: str = "") -> tuple[str, str]:
    if task in PINNED_TASKS:
        return "complex", "pinned: needs strict instruction following"
    return assess_with_reason(text)


CACHE_MIN_PROMPT_TOKENS = 1024


def _read_cache_usage(response: LLMResult) -> tuple[int, int | None, int]:
    usage = (response.llm_output or {}).get("token_usage") or {}
    prompt_tokens = usage.get("prompt_tokens") or 0

    details = usage.get("prompt_tokens_details") or {}
    if not isinstance(details, dict):
        details = getattr(details, "__dict__", {}) or {}

    cached = details.get("cached_tokens")
    written = details.get("cache_write_tokens") or 0

    if cached is None:
        meta = {}
        for batch in response.generations:
            for generation in batch:
                message = getattr(generation, "message", None)
                meta = getattr(message, "usage_metadata", None) or {}
                if meta:
                    break
            if meta:
                break

        prompt_tokens = prompt_tokens or meta.get("input_tokens") or 0
        input_details = meta.get("input_token_details") or {}
        cached = input_details.get("cache_read")
        written = written or input_details.get("cache_creation") or 0

    return prompt_tokens, cached, written


class CacheUsageHandler(BaseCallbackHandler):

    def __init__(self) -> None:
        self._explained_minimum = False

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        try:
            prompt_tokens, cached, written = _read_cache_usage(response)
        except Exception:
            logger.debug("could not read cache usage off the response", exc_info=True)
            return

        model = (response.llm_output or {}).get("model_name") or "?"

        if cached is None:
            logger.debug(
                "prompt cache n/a  model=%s | %s prompt tokens — this response did "
                "not report cached_tokens",
                model, prompt_tokens or "?",
            )
            return

        if cached > 0:
            share = (100 * cached / prompt_tokens) if prompt_tokens else 0.0
            logger.info(
                "prompt cache HIT  model=%-22s | %d/%d prompt tokens served from cache (%.0f%%)%s",
                model, cached, prompt_tokens, share,
                f", {written} written" if written else "",
            )
            return

        if prompt_tokens < CACHE_MIN_PROMPT_TOKENS:
            if not self._explained_minimum:
                logger.info(
                    "prompt cache cannot engage on this call: Azure/OpenAI only "
                    "caches a prefix of at least %d tokens and this prompt is "
                    "under it, so the MISS is by construction, not bad luck — "
                    "prompt_cache_key changes nothing about it. Calls that go "
                    "through src.agent._messages carry SHARED_PREFIX and clear "
                    "the threshold; a short prompt reaching here means some call "
                    "site is building its own message list and bypassing it.",
                    CACHE_MIN_PROMPT_TOKENS,
                )
                self._explained_minimum = True

            logger.info(
                "prompt cache MISS model=%-22s | %d prompt tokens, under the %d-token minimum",
                model, prompt_tokens, CACHE_MIN_PROMPT_TOKENS,
            )
            return

        logger.info(
            "prompt cache MISS model=%-22s | 0/%d prompt tokens from cache — prefix "
            "is long enough, so this is either the first call of the run writing the "
            "entry, or the entry went cold (they expire after a few minutes idle)%s",
            model, prompt_tokens,
            f"; {written} tokens written for the next call" if written else "",
        )


CACHE_LOGGER = CacheUsageHandler()


def supports_prompt_cache(llm) -> bool:
    return isinstance(llm, AzureChatOpenAI)


def build_azure_client(
    credentials: AzureCredentials,
    deployment: str,
    temperature: float = 0.7,
    **overrides,
) -> AzureChatOpenAI:
    """Build a client from an explicit credential set.

    Kept separate from ``get_model`` so the login route can construct a throwaway
    client to probe the credentials before it opens a session, without touching
    the cache or the request context.
    """
    if not deployment:
        raise ValueError("A deployment name is required to build an Azure client.")

    settings = {
        "api_key": credentials.api_key,
        "api_version": credentials.api_version,
        "azure_endpoint": credentials.endpoint,
        "azure_deployment": deployment,
        "temperature": temperature,
        "model_kwargs": {"prompt_cache_key": "langchain-prompt-caching"},
        "callbacks": [CACHE_LOGGER],
    }
    settings.update(overrides)

    return AzureChatOpenAI(**settings)


_MODEL_CACHE: dict[tuple[str, str, float], AzureChatOpenAI] = {}
_CACHE_LOCK = threading.Lock()


def get_model(tier: str = "complex", temperature: float = 0.7) -> AzureChatOpenAI:
    """The client for this tier, built from the current request's credentials.

    Clients are cached per (credentials, deployment, temperature) rather than per
    tier alone, so two users signed in with different Azure resources never share
    a client — the old single-key cache would have handed the second user the
    first user's connection.
    """
    if tier not in TIERS:
        logger.debug("unknown tier %r — treating it as complex", tier)
        tier = "complex"

    credentials = current_credentials()
    deployment = credentials.deployment_for(tier)
    key = (credentials.fingerprint, deployment, temperature)

    with _CACHE_LOCK:
        client = _MODEL_CACHE.get(key)
        if client is not None:
            return client

        client = build_azure_client(credentials, deployment, temperature)
        _MODEL_CACHE[key] = client

    logger.info(
        "built Azure client: %s (tier=%s, creds=%s, cached from here on)",
        deployment, tier, credentials.fingerprint,
    )
    return client


def forget_models(fingerprint: str) -> int:
    """Drop every cached client built from one credential set.

    Called on logout so an API key does not outlive the session that supplied it.
    """
    with _CACHE_LOCK:
        stale = [key for key in _MODEL_CACHE if key[0] == fingerprint]
        for key in stale:
            _MODEL_CACHE.pop(key, None)

    if stale:
        logger.info("dropped %d cached client(s) for creds=%s", len(stale), fingerprint)
    return len(stale)


def clear_model_cache() -> None:
    with _CACHE_LOCK:
        _MODEL_CACHE.clear()


def load_config(temperature: float = 0.7) -> AzureChatOpenAI:
    return get_model("complex", temperature)


def describe_target(tier: str) -> str:
    """Human-readable name of what this tier will call, for the routing log."""
    try:
        credentials = current_credentials()
    except Exception:
        return "azure:(no credentials on this request)"

    deployment = credentials.deployment_for(tier)
    shared = (
        " (shared with complex)"
        if tier == "simple" and not credentials.simple_deployment
        else ""
    )
    return f"azure:{deployment}{shared}"


def model_for(task: str, text: str = "", temperature: float = 0.7) -> AzureChatOpenAI:
    tier, reason = resolve_tier(task, text)
    logger.info(
        "route task=%-11s tier=%-7s -> %s  [%s]",
        task, tier, describe_target(tier), reason,
    )
    return get_model(tier, temperature)
