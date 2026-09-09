import time

from configs.logger import get_logger, preview
from src.agent import write_post
from src.schemas.state import PlatformState
from src.utils.trace import event

logger = get_logger(__name__)


def write_node(state: PlatformState) -> dict:
    platform = state["platform"]
    attempt = state["attempts"] + 1
    problem = state["problem"]
    started = time.perf_counter()

    if problem:
        logger.info(
            "[%s] REVISE attempt %d | acting on critique: %s",
            platform, attempt, preview(problem, limit=200),
        )
        logger.debug(
            "[%s] previous draft (%d chars): %s",
            platform, len(state["draft"]), preview(state["draft"]),
        )
        try:
            draft = write_post(
                platform, state["brief"],
                fix=problem, old_draft=state["draft"],
            )
        except Exception:
            logger.exception(
                "[%s] FAILED revising on attempt %d (fix=%r)",
                platform, attempt, preview(problem, limit=80),
            )
            raise

        action = (
            f"[{platform}] revised (attempt {attempt}) to fix: {problem} "
            f"-> {len(draft)} chars"
        )
        status = "revised"
        detail = f"Rewrote the draft to fix: {problem}"
    else:
        logger.info("[%s] WRITE attempt %d | first draft from the brief", platform, attempt)
        try:
            draft = write_post(platform, state["brief"])
        except Exception:
            logger.exception("[%s] FAILED writing first draft", platform)
            raise

        action = f"[{platform}] wrote first draft ({len(draft)} chars)"
        status = "drafted"
        detail = f"Wrote the first {len(draft)}-character draft from the brief."

    elapsed_ms = round((time.perf_counter() - started) * 1000)

    logger.info(
        "[%s] draft ready | attempt=%d chars=%d elapsed=%d ms",
        platform, attempt, len(draft), elapsed_ms,
    )
    logger.debug("[%s] draft content: %s", platform, preview(draft, limit=300))

    return {
        "draft": draft,
        "attempts": attempt,
        "action_log": [action],
        "trace_events": [
            event(
                "write", platform, status,
                detail=detail, attempt=attempt, started=started,
            )
        ],
    }
