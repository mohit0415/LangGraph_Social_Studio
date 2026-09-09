import operator
from typing import Annotated, Dict, List, TypedDict

from configs.logger import get_logger

logger = get_logger(__name__)


def merge_drafts(left: Dict, right: Dict) -> Dict:
    left = left or {}
    right = right or {}

    overwritten = [k for k in right if k in left and left[k] != right[k]]
    if overwritten:
        logger.debug(
            "merge_drafts: replacing existing draft(s) for %s "
            "(expected during the consistency rewrite, not during fan-out)",
            ", ".join(sorted(overwritten)),
        )

    merged = {**left, **right}
    logger.debug(
        "merge_drafts: %d existing + %d incoming -> %d total (%s)",
        len(left), len(right), len(merged), ", ".join(sorted(merged)) or "empty",
    )
    return merged


class PlatformState(TypedDict):
    brief: str
    platform: str
    draft: str
    problem: str
    attempts: int

    action_log: Annotated[List[str], operator.add]

    trace_events: Annotated[List[Dict], operator.add]


class PlatformOutput(TypedDict):
    drafts: Annotated[Dict, merge_drafts]

    action_log: Annotated[List[str], operator.add]
    trace_events: Annotated[List[Dict], operator.add]


class State(TypedDict):
    topic: str
    brief: str

    drafts: Annotated[Dict, merge_drafts]

    action_log: Annotated[List[str], operator.add]
    trace_events: Annotated[List[Dict], operator.add]
