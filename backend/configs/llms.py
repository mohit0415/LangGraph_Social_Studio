import os
import re
from functools import lru_cache

from dotenv import load_dotenv
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from configs.logger import get_logger

logger = get_logger(__name__)

load_dotenv()


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
                "prompt cache n/a  model=%s | %s prompt tokens — this provider does "
                "not report cached_tokens (expected on the Ollama tier)",
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


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")


@lru_cache(maxsize=1)
def _ollama_is_up() -> bool:
    import urllib.error
    import urllib.request

    url = OLLAMA_BASE_URL.rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(url, timeout=2):
            logger.info("Ollama reachable at %s (model=%s)", OLLAMA_BASE_URL, OLLAMA_MODEL)
            return True
    except urllib.error.HTTPError:
        logger.info("Ollama responding at %s", OLLAMA_BASE_URL)
        return True
    except Exception as exc:
        logger.warning(
            "Ollama not reachable at %s (%s). Simple tier falls back to Azure. "
            "Start it with: ollama serve   (and: ollama pull %s)",
            OLLAMA_BASE_URL, exc, OLLAMA_MODEL,
        )
        return False


def _build_azure(deployment: str, temperature: float) -> AzureChatOpenAI:
    config = {
        "azure_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
        "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
    }

    for key, name in [
        ("api_key", "AZURE_OPENAI_API_KEY"),
        ("azure_endpoint", "AZURE_OPENAI_ENDPOINT"),
        ("api_version", "AZURE_OPENAI_API_VERSION"),
    ]:
        if not config[key]:
            logger.error("Missing %s", name)
            raise ValueError(f"{name} not found in environment variables")

    if not deployment:
        raise ValueError("AZURE_OPENAI_DEPLOYMENT not found in environment variables")

    return AzureChatOpenAI(
        api_key=config["api_key"],
        api_version=config["api_version"],
        azure_endpoint=config["azure_endpoint"],
        azure_deployment=deployment,
        temperature=temperature,
        model_kwargs={
            "prompt_cache_key":"langchain-prompt-caching"
        },
        callbacks=[CACHE_LOGGER],
    )


@lru_cache(maxsize=8)
def get_model(tier: str = "complex", temperature: float = 0.7):
    if tier not in TIERS:
        tier = "complex"

    if tier == "simple" and _ollama_is_up():
        logger.info("built Ollama client: %s (tier=simple, cached from here on)", OLLAMA_MODEL)
        return ChatOpenAI(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            api_key="ollama",
            temperature=temperature,
            callbacks=[CACHE_LOGGER],
        )

    main = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    cheap = os.getenv("AZURE_OPENAI_DEPLOYMENT_SIMPLE")
    deployment = cheap if (tier == "simple" and cheap) else main

    logger.info("built Azure client: %s (tier=%s, cached from here on)", deployment, tier)
    return _build_azure(deployment, temperature)


def load_config(temperature: float = 0.7):
    return get_model("complex", temperature)


def describe_target(tier: str) -> str:
    if tier == "simple" and _ollama_is_up():
        return f"ollama:{OLLAMA_MODEL}"

    main = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    cheap = os.getenv("AZURE_OPENAI_DEPLOYMENT_SIMPLE")
    deployment = cheap if (tier == "simple" and cheap) else main

    suffix = " (ollama down)" if tier == "simple" else ""
    return f"azure:{deployment}{suffix}"


def model_for(task: str, text: str = "", temperature: float = 0.7):
    tier, reason = resolve_tier(task, text)
    logger.info(
        "route task=%-11s tier=%-7s -> %s  [%s]",
        task, tier, describe_target(tier), reason,
    )
    return get_model(tier, temperature)
