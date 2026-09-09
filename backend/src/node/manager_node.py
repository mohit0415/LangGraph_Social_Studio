import time

from configs.logger import get_logger, preview
from src.agent import write_brief
from src.schemas.state import State
from src.utils.trace import event

logger = get_logger(__name__)


def manager_node(state: State) -> dict:
    topic = state["topic"]
    started = time.perf_counter()

    logger.info(
        "[manager] START writing brief | topic_chars=%d | topic=%r",
        len(topic or ""), preview(topic),
    )

    try:
        brief = write_brief(topic)
    except Exception:
        logger.exception("[manager] FAILED writing brief for topic=%r", preview(topic))
        raise

    elapsed_ms = round((time.perf_counter() - started) * 1000)

    logger.info(
        "[manager] DONE brief ready | %d chars in %d ms", len(brief), elapsed_ms,
    )
    logger.debug("[manager] brief content: %s", preview(brief, limit=400))

    return {
        "brief": brief,
        "drafts": {},
        "action_log": [
            f"[manager] wrote the shared brief from the source "
            f"({len(topic or '')} chars in -> {len(brief)} chars out, {elapsed_ms} ms)"
        ],
        "trace_events": [
            event(
                "brief",
                "manager",
                "done",
                detail=(
                    f"Wrote the {len(brief)}-character brief every writer works from, "
                    f"condensed from {len(topic or '')} characters of source material."
                ),
                started=started,
            )
        ],
    }
