from backend.src.agent import write_brief
from backend.src.schemas.state import State


def manager_node(state: State) -> dict:
    """Writes the brief once. No queue/current to seed any more — `fan_out`
    reads the platform list straight off RULES and starts every branch."""
    print("[manager] writing brief...")
    return {
        "brief": write_brief(state["topic"]),
        "drafts": {},
    }
