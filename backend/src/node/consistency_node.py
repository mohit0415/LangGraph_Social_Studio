import time

from configs.logger import get_logger, preview
from src.agent import check_consistency, write_post
from src.schemas.state import State
from src.utils.trace import event

logger = get_logger(__name__)


def consistency_node(state: State) -> dict:
    drafts = state["drafts"]
    platforms = sorted(drafts)
    started = time.perf_counter()

    logger.info(
        "[consistency] START comparing %d posts across %s",
        len(drafts), ", ".join(platforms) or "(none)",
    )
    for platform in platforms:
        logger.debug(
            "[consistency] %s draft is %d chars", platform, len(drafts[platform])
        )

    try:
        conflicts = check_consistency(state["brief"], drafts)
    except Exception:
        logger.exception(
            "[consistency] comparison FAILED; shipping the posts unreconciled"
        )
        conflicts = {}

    if not conflicts:
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        logger.info(
            "[consistency] DONE — %d posts agree, no contradictions found (%d ms)",
            len(drafts), elapsed_ms,
        )
        return {
            "action_log": [
                f"[consistency] compared {len(drafts)} posts "
                f"({', '.join(platforms)}) — no contradictions found"
            ],
            "trace_events": [
                event(
                    "consistency", "consistency", "ok",
                    detail=(
                        f"Compared {len(drafts)} posts ({', '.join(platforms)}) "
                        f"against the brief and each other; found no contradictions."
                    ),
                    started=started,
                )
            ],
        }

    logger.warning(
        "[consistency] found %d contradiction(s) in %s",
        len(conflicts), ", ".join(sorted(conflicts)),
    )

    fixed_drafts = dict(drafts)
    log = []
    events = []

    for platform, problem in conflicts.items():
        fix_started = time.perf_counter()
        logger.info(
            "[consistency] rewriting %s to resolve: %s",
            platform, preview(problem, limit=200),
        )
        try:
            fixed_drafts[platform] = write_post(
                platform, state["brief"], fix=problem, old_draft=fixed_drafts[platform]
            )
        except Exception:
            logger.exception(
                "[consistency] FAILED rewriting %s; keeping the original draft", platform
            )
            log.append(
                f"[consistency] could not fix {platform} ({problem}) — kept the original"
            )
            events.append(
                event("consistency", "consistency", "problem",
                      detail=f"{platform}: rewrite failed, kept the original draft.")
            )
            continue

        fix_ms = round((time.perf_counter() - fix_started) * 1000)
        logger.info(
            "[consistency] %s reconciled in %d ms | %d -> %d chars",
            platform, fix_ms, len(drafts[platform]), len(fixed_drafts[platform]),
        )
        log.append(f"[consistency] fixed {platform} — contradiction was: {problem}")
        events.append(
            event("consistency", "consistency", "fixed",
                  detail=f"Rewrote the {platform} post to resolve: {problem}")
        )

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    logger.info(
        "[consistency] DONE — reconciled %d of %d posts in %d ms",
        len(conflicts), len(drafts), elapsed_ms,
    )

    events.append(
        event(
            "consistency", "consistency", "done",
            detail=(
                f"Reconciled {len(conflicts)} of {len(drafts)} posts "
                f"({', '.join(sorted(conflicts))})."
            ),
            started=started,
        )
    )

    return {"drafts": fixed_drafts, "action_log": log, "trace_events": events}
