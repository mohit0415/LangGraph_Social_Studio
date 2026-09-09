import time
import uuid

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from configs.credentials import AzureCredentials, MissingCredentialsError
from configs.database import connect, db_path
from configs.logger import get_logger, preview
from src.agent import RULES, route_message, write_post
from src.graphs.graph import build_checkpointer, build_graph
from src.models.models import SocialInput
from src.routes.auth import require_credentials, session_store
from src.routes.auth import router as auth_router
from src.store.thread_store import ThreadStore
from src.utils.trace import event
from src.callbacks.langfuse_callback import build_run_config, get_langfuse_manager
from typing import Any, Optional, Tuple

logger = get_logger(__name__)

app = FastAPI(title="Autonomous Social Media Content Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

checkpointer = build_checkpointer()
workflow_graph = build_graph(checkpointer)
print(workflow_graph.get_graph().draw_mermaid())

threads_store = ThreadStore(connect("threads"))

langfuse_manager = get_langfuse_manager()

logger.info(
    "studio API ready | %d platforms configured: %s | database=%s | Azure "
    "credentials come from /auth/login, never from the environment",
    len(RULES),
    ", ".join(f"{name} (<={rule['max_chars']} chars)" for name, rule in RULES.items()),
    db_path(),
)


@app.exception_handler(MissingCredentialsError)
async def _no_credentials(request: Request, exc: MissingCredentialsError) -> JSONResponse:
    """A model was requested with nothing bound to the request context.

    Reaching this means a route is missing `require_credentials`, so answer 401
    rather than a 500 — the browser's 401 handling sends the user back to the
    login page, which is where the credentials come from.
    """
    logger.error("%s %s reached the model layer unauthenticated", request.method, request.url.path)
    return JSONResponse(status_code=401, content={"detail": str(exc)})


def _thread_payload(thread_id: str, state: dict, **extra) -> dict:
    payload = {
        "thread_id": thread_id,
        "brief": state.get("brief", ""),
        "posts": state.get("drafts", {}),
        "trace": state.get("action_log", []),
        "events": state.get("trace_events", []),
        "messages": threads_store.messages(thread_id),
    }
    payload.update(extra)
    return payload


def _load_state(thread_id: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    state = workflow_graph.get_state(config).values

    if not state.get("drafts"):
        logger.warning(
            "thread %s has no saved drafts in the checkpoint (unknown or deleted id)",
            thread_id,
        )
        raise HTTPException(status_code=404, detail="Unknown thread_id.")

    return state


def _run_workflow(query: str) -> dict:
    thread_id = str(uuid.uuid4())
    config, _handler = build_run_config(thread_id, trace_name="new_run", tags=["new"])
    started = time.perf_counter()
    state = {
        "topic": query,
        "brief": "",
        "drafts": {},
        "action_log": [],
        "trace_events": [],
    }

    logger.info(
        "NEW RUN thread=%s | source is %d chars: %s",
        thread_id, len(query or ""), preview(query, limit=150),
    )

    try:
        result = workflow_graph.invoke(state, config=config)
    except Exception:
        logger.exception(
            "NEW RUN FAILED thread=%s after %d ms | source: %s",
            thread_id, round((time.perf_counter() - started) * 1000), preview(query),
        )
        raise HTTPException(status_code=500, detail="Content generation failed.")

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    drafts = result["drafts"]
    logger.info(
        "NEW RUN DONE thread=%s in %d ms | %d posts (%s) | %d log lines, %d trace events",
        thread_id, elapsed_ms, len(drafts),
        ", ".join(f"{p}:{len(t)}c" for p, t in sorted(drafts.items())),
        len(result["action_log"]), len(result.get("trace_events", [])),
    )

    missing = [p for p in RULES if p not in drafts]
    if missing:
        logger.error(
            "NEW RUN thread=%s produced no draft for %s — the branch did not return",
            thread_id, ", ".join(missing),
        )

    threads_store.record(thread_id, query)
    threads_store.append_messages(thread_id, [{"role": "user", "text": query}])

    return _thread_payload(thread_id, result, action="new")


def _clarify(thread_id: str, saved: dict, intent) -> dict:
    known = list(saved["drafts"])

    if intent.platforms and not intent.instruction.strip():
        named = " and ".join(intent.platforms)
        message = f"What should I change about the {named} post?"
    elif intent.instruction.strip():
        message = f"Which post should I apply that to? ({intent.instruction})"
    else:
        message = "Which post should I change, and what should I change about it?"

    logger.info(
        "CLARIFY thread=%s | router gave platforms=%s instruction=%r — asking instead "
        "of guessing an edit | question: %s",
        thread_id,
        ",".join(intent.platforms) or "(none)",
        preview(intent.instruction, limit=80),
        message,
    )
    logger.debug("CLARIFY thread=%s offering options: %s", thread_id, known + ["all"])

    return _thread_payload(
        thread_id, saved,
        action="clarify",
        message=message,
        options=known + ["all"],
    )


def _refine(
    thread_id: str,
    saved: dict,
    targets: list[str],
    instruction: str,
    query: str = "",
) -> dict:
    config, _handler = build_run_config(
        thread_id, trace_name="refine", tags=["refine"],
    )
    state_config = {"configurable": {"thread_id": thread_id}}
    run_started = time.perf_counter()

    requested = list(targets)
    targets = [p for p in requested if p in saved["drafts"]]

    unknown = [p for p in requested if p not in saved["drafts"]]
    if unknown:
        logger.warning(
            "REFINE thread=%s asked for %s, which this thread has no draft for; "
            "refining only %s",
            thread_id, ", ".join(unknown), ", ".join(targets) or "nothing",
        )

    logger.info(
        "REFINE thread=%s | targets=%s | instruction: %s",
        thread_id, ", ".join(targets) or "(none)", preview(instruction, limit=150),
    )

    revised_posts = {}
    log_entries = []
    trace_events = []
    for target in targets:
        started = time.perf_counter()
        original_len = len(saved["drafts"][target])
        try:
            revised_posts[target] = write_post(
                target,
                saved["brief"],
                fix=instruction,
                old_draft=saved["drafts"][target],
                config=config,
            )
        except Exception:
            logger.exception(
                "REFINE FAILED thread=%s platform=%s | instruction: %s",
                thread_id, target, preview(instruction, limit=120),
            )
            raise HTTPException(status_code=500, detail="Refinement failed.")

        new_len = len(revised_posts[target])
        logger.info(
            "REFINE ok thread=%s platform=%s | %d -> %d chars in %d ms",
            thread_id, target, original_len, new_len,
            round((time.perf_counter() - started) * 1000),
        )

        log_entries.append(
            f"[{target}] refined on request: {instruction} "
            f"({original_len} -> {new_len} chars)"
        )
        trace_events.append(
            event("refine", target, "refined", detail=instruction, started=started)
        )

    workflow_graph.update_state(
        state_config,
        {
            "drafts": revised_posts,
            "action_log": log_entries,
            "trace_events": trace_events,
        },
    )
    updated = workflow_graph.get_state(state_config).values

    threads_store.append_messages(thread_id, [
        {"role": "user", "text": query},
        {
            "role": "system",
            "text": f"Refined {', '.join(targets)} — {instruction}",
        },
    ])

    logger.info(
        "REFINE DONE thread=%s | %d of %d posts rewritten in %d ms | untouched: %s",
        thread_id, len(revised_posts), len(saved["drafts"]),
        round((time.perf_counter() - run_started) * 1000),
        ", ".join(p for p in saved["drafts"] if p not in revised_posts) or "none",
    )

    return _thread_payload(
        thread_id, updated,
        action="refine",
        refined=targets,
        instruction=instruction,
    )

def setup_langfuse_callback(
    session_id: str,
    trace_name: str = "ask",
    user_id: Optional[str] = None,
) -> Tuple[dict, Optional[Any]]:
    return build_run_config(session_id, trace_name=trace_name, user_id=user_id)


async def flush_langfuse_traces(callback_handler: Optional[Any] = None) -> None:
    import asyncio

    try:
        await asyncio.to_thread(langfuse_manager.flush)
    except Exception:
        logger.debug("langfuse flush failed (ignored)", exc_info=True)


@app.on_event("shutdown")
def _shutdown_langfuse() -> None:
    langfuse_manager.shutdown()


@app.post("/ask")
async def social_query(
    ques: SocialInput,
    credentials: AzureCredentials = Depends(require_credentials),
):
    logger.info(
        "POST /ask | thread=%s | creds=%s deployment=%s | query (%d chars): %s",
        ques.thread_id or "(none -> new run)",
        credentials.fingerprint, credentials.deployment,
        len(ques.query or ""), preview(ques.query, limit=150),
    )

    try:
        if not ques.thread_id:
            return _run_workflow(ques.query)

        saved = _load_state(ques.thread_id)

        logger.debug(
            "thread=%s resumed with %d saved posts (%s) and %d action-log lines",
            ques.thread_id, len(saved["drafts"]), ", ".join(sorted(saved["drafts"])),
            len(saved.get("action_log") or []),
        )

        router_config, _ = setup_langfuse_callback(ques.thread_id, trace_name="router")
        intent = route_message(
            ques.query, saved.get("action_log"), config=router_config,
        )
        if intent.action == "new":
            logger.info(
                "thread=%s: router read this as FRESH source material, not a "
                "follow-up — starting a new thread",
                ques.thread_id,
            )
            return _run_workflow(ques.query)

        if not intent.platforms or not intent.instruction.strip():
            return _clarify(ques.thread_id, saved, intent)

        return _refine(
            ques.thread_id, saved, intent.platforms, intent.instruction,
            query=ques.query,
        )
    finally:
        await flush_langfuse_traces()


@app.get("/threads")
def list_threads(credentials: AzureCredentials = Depends(require_credentials)):
    logger.info("GET /threads")
    return {"threads": threads_store.list_all()}


@app.get("/threads/{thread_id}")
def get_thread(
    thread_id: str,
    credentials: AzureCredentials = Depends(require_credentials),
):
    logger.info("GET /threads/%s", thread_id)
    state = _load_state(thread_id)
    return _thread_payload(thread_id, state, action="load")


@app.delete("/threads/{thread_id}")
def delete_thread(
    thread_id: str,
    credentials: AzureCredentials = Depends(require_credentials),
):
    logger.info("DELETE /threads/%s", thread_id)

    removed_from_index = threads_store.delete(thread_id)

    try:
        checkpointer.delete_thread(thread_id)
        logger.info("deleted checkpoints for thread %s", thread_id)
    except Exception:
        logger.exception(
            "failed deleting checkpoints for thread %s; the index row was removed "
            "so the thread is no longer listed, but its graph state remains on disk",
            thread_id,
        )

    if not removed_from_index:
        logger.warning("DELETE /threads/%s: no index row existed", thread_id)

    return {"thread_id": thread_id, "deleted": True}


@app.get("/platforms")
def platforms():
    logger.debug("GET /platforms -> serving %d platform limits from RULES", len(RULES))
    return {
        "platforms": [
            {"id": name, "max_chars": rule["max_chars"]}
            for name, rule in RULES.items()
        ]
    }


@app.get("/health")
def health():
    logger.debug("GET /health -> ok")
    return {
        "status": "ok",
        "database": str(db_path()),
        "credentials": "per-session (supplied at /auth/login)",
        "active_sessions": len(session_store),
    }


if __name__ == "__main__":
    logger.info("starting uvicorn on http://0.0.0.0:8000 (reload=True)")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
