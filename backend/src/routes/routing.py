from langgraph.types import Send

from configs.logger import get_logger, preview
from src.agent import RULES
from src.schemas.state import PlatformState, State

logger = get_logger(__name__)

MAX_ATTEMPTS = 3


def after_self_check(state: PlatformState) -> str:
    platform = state["platform"]
    attempts = state["attempts"]
    problem = state["problem"]

    if problem and attempts < MAX_ATTEMPTS:
        logger.info(
            "[%s] ROUTE -> revise | attempt %d of %d, unresolved: %s",
            platform, attempts, MAX_ATTEMPTS, preview(problem, limit=150),
        )
        return "revise"

    if problem:
        logger.warning(
            "[%s] ROUTE -> accept | attempt budget exhausted (%d/%d) with the "
            "problem still open: %s",
            platform, attempts, MAX_ATTEMPTS, preview(problem, limit=150),
        )
    else:
        logger.info(
            "[%s] ROUTE -> accept | clean after %d attempt(s)", platform, attempts,
        )
    return "accept"


def fan_out(state: State) -> list[Send]:
    platforms = list(RULES)
    logger.info(
        "[fan-out] starting %d platform branches in parallel: %s | brief=%d chars",
        len(platforms), ", ".join(platforms), len(state.get("brief") or ""),
    )

    sends = [
        Send("platform", {
            "brief": state["brief"],
            "platform": p,
            "draft": "",
            "problem": "",
            "attempts": 0,
            "action_log": [],
            "trace_events": [],
        })
        for p in platforms
    ]

    logger.debug(
        "[fan-out] each branch may take up to %d write/self-check attempts",
        MAX_ATTEMPTS,
    )
    return sends
