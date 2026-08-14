import operator
from typing import Annotated, Dict, List, TypedDict


def merge_drafts(left: Dict, right: Dict) -> Dict:
    """Reducer: lets parallel branches each write their own key into `drafts`
    without clobbering each other. Without this, two branches finishing at the
    same time would raise an InvalidUpdateError."""
    return {**(left or {}), **(right or {})}


class PlatformState(TypedDict):
    """State of ONE platform branch. Lives only inside the per-platform subgraph,
    so `draft` / `problem` / `attempts` can never be overwritten by a sibling
    platform running at the same time."""
    brief: str
    platform: str
    draft: str
    problem: str
    attempts: int

    action_log: Annotated[List[str], operator.add]


class PlatformOutput(TypedDict):
    """The ONLY thing a platform branch is allowed to hand back to the parent.
    Keeps `brief` (and everything else) out of the return value — otherwise all
    three branches would write `brief` in the same step and LangGraph would
    raise InvalidUpdateError."""
    drafts: Annotated[Dict, merge_drafts]

    action_log: Annotated[List[str], operator.add]


class State(TypedDict):
    """Top-level state. No `queue` / `current` any more — there is no single
    'platform being worked on' when every platform runs at once."""
    topic: str
    brief: str

    drafts: Annotated[Dict, merge_drafts]

    action_log: Annotated[List[str], operator.add]
