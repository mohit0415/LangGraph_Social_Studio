import time
from typing import Literal

from pydantic import BaseModel

from configs.llms import model_for, supports_prompt_cache
from configs.logger import get_logger, preview

from src.utils.prompts import (
    CONSISTENCY_SYSTEM,
    CONSISTENCY_TASK,
    ROUTER_SYSTEM,
    ROUTER_TASK,
    MANAGER_SYSTEM,
    MANAGER_TASK,
    SELF_CHECK_SYSTEM,
    SELF_CHECK_TASK,
    SELF_CHECK_REVISION_TASK,
    REVISE_TASK,
    SHARED_PREFIX,
    WRITE_TASK,
    WRITER_SYSTEM,
)

logger = get_logger(__name__)


def _messages(llm, system: str, user: str) -> list[tuple[str, str]]:
    if not supports_prompt_cache(llm):
        return [("system", system), ("human", user)]

    return [("system", SHARED_PREFIX), ("system", system), ("human", user)]


def ask(
    system: str,
    user: str,
    task: str = "write",
    routing_text: str = "",
    config: dict | None = None,
) -> str:
    started = time.perf_counter()
    llm = model_for(task, routing_text)

    logger.debug(
        "llm call task=%s | system=%d chars, user=%d chars | explicit config=%s",
        task, len(system), len(user), bool(config),
    )

    extra = {"config": config} if config else {}

    try:
        response = llm.invoke(_messages(llm, system, user), **extra)
    except Exception:
        logger.exception(
            "llm call FAILED task=%s after %d ms",
            task, round((time.perf_counter() - started) * 1000),
        )
        raise

    text = response.content.strip()
    logger.info(
        "llm call ok task=%-11s | %d chars in %d ms",
        task, len(text), round((time.perf_counter() - started) * 1000),
    )
    logger.debug("llm response task=%s: %s", task, preview(text))
    return text


def ask_structured(
    schema,
    system: str,
    user: str,
    task: str,
    fallback,
    config: dict | None = None,
):
    started = time.perf_counter()
    llm = model_for(task)

    logger.debug(
        "structured call task=%s schema=%s | user=%d chars",
        task, schema.__name__, len(user),
    )

    extra = {"config": config} if config else {}

    try:
        result = llm.with_structured_output(schema).invoke(
            _messages(llm, system, user), **extra
        )
    except Exception:
        logger.exception(
            "structured output FAILED task=%s schema=%s after %d ms",
            task, schema.__name__, round((time.perf_counter() - started) * 1000),
        )
        logger.warning(
            "falling back for task=%s -> %r (the request continues degraded)",
            task, fallback,
        )
        return fallback

    logger.info(
        "structured call ok task=%-11s schema=%-17s | %d ms",
        task, schema.__name__, round((time.perf_counter() - started) * 1000),
    )
    logger.debug("structured result task=%s: %r", task, result)
    return result


RULES = {
    "linkedin": {
        "max_chars": 3000,
        "style": (
            "Professional but human — write like a practitioner, not a brand account. "
            "Hook in the first line. Short paragraphs with a blank line between each. "
            "One concrete example beats three adjectives. "
            "End with a question or clear CTA. 3-5 hashtags."
        ),
    },
    "x": {
        "max_chars": 280,
        "style": (
            "One punchy idea, nothing else. No preamble. Cut every filler word. "
            "Opinionated beats balanced. Max 2 hashtags, ideally zero."
        ),
    },
    "instagram": {
        "max_chars": 2200,
        "style": (
            "Warm and conversational, like talking to one person. "
            "Hook in the first two lines. Short lines with breaks. "
            "Emojis are fine, don't overdo it. CTA, then 8-15 hashtags on the last line."
        ),
    },
}


def write_brief(topic: str) -> str:
    logger.debug("write_brief: condensing %d chars of source material", len(topic or ""))
    return ask(
        MANAGER_SYSTEM,
        MANAGER_TASK.format(topic=topic),
        task="brief",
        routing_text=topic,
    )


def write_post(
    platform: str,
    brief: str,
    fix: str = "",
    old_draft: str = "",
    config: dict | None = None,
) -> str:
    if platform not in RULES:
        logger.error(
            "write_post called with unknown platform %r (known: %s)",
            platform, ", ".join(RULES),
        )
        raise KeyError(f"Unknown platform {platform!r}")

    rules = RULES[platform]
    logger.debug(
        "write_post platform=%s mode=%s | brief=%d chars, limit=%d chars",
        platform, "revise" if fix else "fresh", len(brief), rules["max_chars"],
    )
    system = WRITER_SYSTEM.format(
        platform=platform, style=rules["style"], max_chars=rules["max_chars"]
    )
    if fix:
        user = REVISE_TASK.format(brief=brief, old_draft=old_draft, fix=fix)
    else:
        user = WRITE_TASK.format(brief=brief, platform=platform)

    return ask(system, user, task="write", routing_text=brief, config=config)


def check_length(platform: str, draft: str) -> str:
    limit = RULES[platform]["max_chars"]
    length = len(draft)

    if length > limit:
        overflow = length - limit
        logger.info(
            "[%s] length check FAILED: %d chars vs %d limit (%d over, %.0f%% of budget)",
            platform, length, limit, overflow, 100 * length / limit,
        )
        return (f"Too long: {length} characters, limit is {limit}. "
                f"Cut at least {overflow} characters. Keep the hook.")

    logger.debug(
        "[%s] length check passed: %d/%d chars (%.0f%% of budget)",
        platform, length, limit, 100 * length / limit,
    )
    return ""


MAX_CRITIQUE_CHARS = 400


def _is_ok(verdict: str) -> bool:
    cleaned = verdict.strip().strip('"\'*`.').strip()
    if cleaned.upper().startswith("OK"):
        logger.debug("verdict parsed as OK (leading form): %r", preview(cleaned, 60))
        return True

    lines = [ln.strip().strip('"\'*`.').strip() for ln in cleaned.splitlines() if ln.strip()]
    if lines and lines[-1].upper() == "OK":
        logger.debug("verdict parsed as OK (verdict on the last line of %d)", len(lines))
        return True

    return False


def _is_malformed(verdict: str) -> bool:
    if len(verdict) > MAX_CRITIQUE_CHARS:
        logger.debug(
            "verdict is malformed by length: %d chars > %d allowed",
            len(verdict), MAX_CRITIQUE_CHARS,
        )
        return True

    markers = ("## check", "## how to answer", "## reviewing", "## final pass",
               "1. message", "2. facts", "3. tone", "4. hook")
    lowered = verdict.lower()
    for marker in markers:
        if marker in lowered:
            logger.debug("verdict is malformed: echoed the checklist marker %r", marker)
            return True
    return False


def self_critique(
    platform: str,
    brief: str,
    draft: str,
    attempt: int = 1,
    previous_problem: str = "",
    max_attempts: int = 3,
) -> str:
    logger.debug(
        "[%s] critique attempt %d/%d | draft=%d chars | mode=%s",
        platform, attempt, max_attempts, len(draft),
        "revision review" if (previous_problem and attempt > 1) else "first review",
    )

    if previous_problem and attempt > 1:
        is_final = attempt >= max_attempts
        if is_final:
            logger.info(
                "[%s] FINAL critique pass (attempt %d/%d) — the critic is told to "
                "accept unless the draft is factually wrong or off-brief",
                platform, attempt, max_attempts,
            )
        logger.debug(
            "[%s] showing the critic its own previous note: %s",
            platform, preview(previous_problem, limit=150),
        )
        user = SELF_CHECK_REVISION_TASK.format(
            brief=brief,
            draft=draft,
            previous_problem=previous_problem,
            attempt=attempt,
            max_attempts=max_attempts,
            final_warning=(
                " This is the FINAL pass — accept unless the draft is factually "
                "wrong or off-brief." if is_final else ""
            ),
        )
    else:
        user = SELF_CHECK_TASK.format(brief=brief, draft=draft)

    verdict = ask(
        SELF_CHECK_SYSTEM.format(platform=platform),
        user,
        task="critique",
        routing_text=brief,
    )

    if not verdict.strip():
        logger.warning(
            "[%s] critic returned an EMPTY verdict on attempt %d; "
            "reading that as approval and accepting the draft",
            platform, attempt,
        )
        return ""

    if _is_ok(verdict):
        logger.info(
            "[%s] critic verdict on attempt %d/%d: OK — no changes requested",
            platform, attempt, max_attempts,
        )
        return ""

    if _is_malformed(verdict):
        logger.warning(
            "[%s] critic returned a MALFORMED verdict on attempt %d (%d chars, "
            "limit %d) — it echoed its own checklist instead of reviewing. "
            "Accepting the draft rather than handing this back to the writer as "
            "a revision instruction. Verdict starts: %s",
            platform, attempt, len(verdict), MAX_CRITIQUE_CHARS,
            preview(verdict, limit=120),
        )
        return ""

    problem = verdict.strip()
    logger.info(
        "[%s] critic verdict on attempt %d/%d: NEEDS WORK — %s",
        platform, attempt, max_attempts, preview(problem, limit=200),
    )
    return problem


class RefineIntent(BaseModel):
    action: Literal["refine", "new"]
    platforms: list[Literal["linkedin", "x", "instagram"]]
    instruction: str


def route_message(
    message: str,
    action_log: list[str] | None = None,
    config: dict | None = None,
) -> RefineIntent:
    edits = [line for line in (action_log or []) if "refined on request:" in line]
    history = "\n".join(edits[-5:]) or "(no edits yet - this is the first change)"

    logger.info(
        "routing follow-up message (%d chars) with %d prior edit(s) as context: %s",
        len(message), len(edits), preview(message, limit=150),
    )
    logger.debug("router history window:\n%s", history)

    intent = ask_structured(
        RefineIntent,
        ROUTER_SYSTEM,
        ROUTER_TASK.format(message=message, history=history),
        task="router",
        fallback=RefineIntent(action="refine", platforms=[], instruction=""),
        config=config,
    )

    logger.info(
        "router decided action=%s platforms=%s instruction=%r",
        intent.action,
        ",".join(intent.platforms) or "(none -> will clarify)",
        preview(intent.instruction, limit=120),
    )
    return intent


class Conflict(BaseModel):
    platform: Literal["linkedin", "x", "instagram"]
    problem: str


class ConsistencyReport(BaseModel):
    conflicts: list[Conflict]


def check_consistency(brief: str, drafts: dict) -> dict:
    posts = "\n\n".join(f"--- {p.upper()} ---\n{t}" for p, t in drafts.items())

    logger.debug(
        "consistency check across %d posts (%s), %d chars of combined text",
        len(drafts), ", ".join(sorted(drafts)), len(posts),
    )

    report = ask_structured(
        ConsistencyReport,
        CONSISTENCY_SYSTEM,
        CONSISTENCY_TASK.format(brief=brief, posts=posts),
        task="consistency",
        fallback=ConsistencyReport(conflicts=[]),
    )
    ignored = [c.platform for c in report.conflicts if c.platform.lower() not in drafts]
    if ignored:
        logger.warning(
            "consistency report named %d platform(s) not in this run (%s); ignoring them",
            len(ignored), ", ".join(ignored),
        )

    conflicts = {
        c.platform.lower(): c.problem
        for c in report.conflicts
        if c.platform.lower() in drafts
    }

    if conflicts:
        for platform, problem in conflicts.items():
            logger.info(
                "consistency conflict on %s: %s", platform, preview(problem, limit=200)
            )
    else:
        logger.debug("consistency check found no conflicts")

    return conflicts
