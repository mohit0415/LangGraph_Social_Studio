import time

from configs.logger import get_logger

logger = get_logger(__name__)

STAGE_ORDER = {
    "brief": 0,
    "write": 1,
    "self_check": 2,
    "accept": 3,
    "consistency": 4,
    "refine": 5,
}


def event(
    step: str,
    actor: str,
    status: str,
    detail: str = "",
    attempt: int | None = None,
    started: float | None = None,
) -> dict:
    if step not in STAGE_ORDER:
        logger.warning(
            "trace event has an unknown step %r (known: %s); it will sort last in the UI",
            step, ", ".join(STAGE_ORDER),
        )

    duration_ms = round((time.perf_counter() - started) * 1000) if started else None

    record = {
        "step": step,
        "actor": actor,
        "status": status,
        "detail": detail,
        "attempt": attempt,
        "stage": STAGE_ORDER.get(step, 99),
        "ts": time.time(),
        "duration_ms": duration_ms,
    }

    logger.debug(
        "trace event | step=%-11s actor=%-10s status=%-14s attempt=%s duration=%s",
        step, actor, status,
        attempt if attempt is not None else "-",
        f"{duration_ms} ms" if duration_ms is not None else "-",
    )
    return record
