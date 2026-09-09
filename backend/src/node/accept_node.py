from configs.logger import get_logger, preview
from src.schemas.state import PlatformState
from src.utils.trace import event

logger = get_logger(__name__)


def accept_node(state: PlatformState) -> dict:
    platform = state["platform"]
    attempts = state["attempts"]
    draft = state["draft"]
    problem = state["problem"]

    if problem:
        logger.warning(
            "[%s] ACCEPTED AS-IS after exhausting %d attempts | unresolved: %s",
            platform, attempts, preview(problem, limit=200),
        )
        action = (
            f"[{platform}] accepted as-is after {attempts} attempt(s) — "
            f"unresolved note from the critic: {problem}"
        )
        status = "accepted_as_is"
        detail = (
            f"Shipping with a known issue after {attempts} attempts: {problem}"
        )
    else:
        logger.info(
            "[%s] ACCEPTED on attempt %d | final draft=%d chars",
            platform, attempts, len(draft),
        )
        action = (
            f"[{platform}] accepted after {attempts} attempt(s) — "
            f"final draft is {len(draft)} chars"
        )
        status = "accepted"
        detail = (
            f"Passed review on attempt {attempts} of {attempts}; "
            f"final draft is {len(draft)} characters."
        )

    logger.debug("[%s] final draft: %s", platform, preview(draft, limit=300))

    return {
        "drafts": {platform: draft},
        "action_log": [action],
        "trace_events": [
            event("accept", platform, status, detail=detail, attempt=attempts)
        ],
    }
