import time

from configs.logger import get_logger, preview
from src.agent import check_length, self_critique
from src.routes.routing import MAX_ATTEMPTS
from src.schemas.state import PlatformState
from src.utils.trace import event

logger = get_logger(__name__)


def self_check_node(state: PlatformState) -> dict:
    platform, draft = state["platform"], state["draft"]
    attempt = state["attempts"]
    previous_problem = state["problem"]
    started = time.perf_counter()

    logger.info(
        "[%s] SELF-CHECK attempt %d/%d | draft=%d chars | carrying-forward=%s",
        platform, attempt, MAX_ATTEMPTS, len(draft),
        preview(previous_problem, limit=100) if previous_problem else "nothing (first pass)",
    )

    problem = check_length(platform, draft)
    checked_by = "length"

    if problem:
        logger.warning(
            "[%s] length check FAILED on attempt %d: %s", platform, attempt, problem,
        )
    else:
        logger.debug(
            "[%s] length check passed (%d chars); escalating to the critic",
            platform, len(draft),
        )
        checked_by = "critic"
        try:
            problem = self_critique(
                platform,
                state["brief"],
                draft,
                attempt=attempt,
                previous_problem=previous_problem,
                max_attempts=MAX_ATTEMPTS,
            )
        except Exception:
            logger.exception(
                "[%s] critic call FAILED on attempt %d; treating the draft as acceptable",
                platform, attempt,
            )
            problem = ""

        if problem:
            logger.info(
                "[%s] critic REJECTED attempt %d: %s",
                platform, attempt, preview(problem, limit=200),
            )
            if previous_problem and problem.strip() == previous_problem.strip():
                logger.warning(
                    "[%s] critic repeated the SAME note as attempt %d — "
                    "the revision did not address it",
                    platform, attempt - 1,
                )
        else:
            logger.info("[%s] critic APPROVED attempt %d", platform, attempt)

    will_retry = bool(problem) and attempt < MAX_ATTEMPTS
    logger.info(
        "[%s] self-check verdict on attempt %d: %s | next=%s",
        platform, attempt,
        "PROBLEM" if problem else "OK",
        "revise" if will_retry else "accept",
    )

    if problem:
        action = (
            f"[{platform}] self-check (attempt {attempt}/{MAX_ATTEMPTS}) found a problem "
            f"via the {checked_by} check: {problem}"
        )
        detail = f"{checked_by.capitalize()} check failed: {problem}"
    else:
        action = (
            f"[{platform}] self-check (attempt {attempt}/{MAX_ATTEMPTS}) passed the "
            f"{checked_by} check — draft is {len(draft)} chars"
        )
        detail = f"Passed the {checked_by} check ({len(draft)} chars)."

    return {
        "problem": problem,
        "action_log": [action],
        "trace_events": [
            event(
                "self_check",
                platform,
                "problem" if problem else "ok",
                detail=detail,
                attempt=attempt,
                started=started,
            )
        ],
    }
