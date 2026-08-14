from backend.src.agent import write_post
from backend.src.schemas.state import PlatformState


def write_node(state: PlatformState) -> dict:
    """Writes a fresh draft, or revises the last one if self_check found a problem.

    Only change: reads `platform` (branch-local) instead of `current` (global).
    """
    platform = state["platform"]
    attempt = state["attempts"] + 1

    if state["problem"]:
        print(f"[{platform}] self-correcting (attempt {attempt})")
        draft = write_post(
            platform, state["brief"],
            fix=state["problem"], old_draft=state["draft"],
        )
        action = f"[{platform}] revised (attempt {attempt}): {state['problem']}"
    else:
        print(f"[{platform}] writing...")
        draft = write_post(platform, state["brief"])
        action = f"[{platform}] wrote first draft"
    return {"draft": draft, "attempts": attempt, "action_log": [action]}
