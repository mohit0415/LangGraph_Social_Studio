"""Sign-in with Azure OpenAI credentials.

The login page is where the Azure endpoint, key, deployment and API version are
entered; this router is what receives them. It verifies them against Azure with
one tiny completion, keeps them in an in-memory session, and hands the browser
an opaque session id. Every later request carries only that id, and the
``require_credentials`` dependency turns it back into credentials bound to the
request context for the LLM layer to pick up.
"""

from __future__ import annotations

import time
from typing import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from configs.credentials import (
    DEFAULT_API_VERSION,
    AzureCredentials,
    reset_credentials,
    set_credentials,
)
from configs.llms import build_azure_client, forget_models
from configs.logger import get_logger
from src.store.session_store import Session, SessionStore

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

SESSION_HEADER = "X-Session-Id"

session_store = SessionStore()

PROBE_PROMPT = [("human", "ping")]
PROBE_TIMEOUT_SECONDS = 20


class LoginRequest(BaseModel):
    endpoint: str = Field(..., description="https://<resource>.openai.azure.com")
    api_key: str = Field(..., description="Azure OpenAI API key — never stored on disk")
    deployment: str = Field(..., description="Deployment name for the complex tier")
    api_version: str = Field(default=DEFAULT_API_VERSION)
    simple_deployment: str = Field(
        default="",
        description="Optional cheaper deployment for the simple tier; "
        "blank means the simple tier reuses `deployment`.",
    )


def _probe(credentials: AzureCredentials) -> None:
    """Make the smallest possible real call, so a bad key fails at the login page.

    Without this the first sign of a wrong key or deployment is a 500 from deep
    inside the graph, several seconds into a generation run.
    """
    started = time.perf_counter()
    client = build_azure_client(
        credentials,
        credentials.deployment,
        temperature=0.0,
        max_tokens=1,
        max_retries=0,
        timeout=PROBE_TIMEOUT_SECONDS,
        callbacks=[],
    )

    try:
        client.invoke(PROBE_PROMPT)
    except Exception as exc:
        elapsed = round((time.perf_counter() - started) * 1000)
        logger.warning(
            "credential probe FAILED in %d ms for endpoint=%s deployment=%s: %s",
            elapsed, credentials.endpoint, credentials.deployment, exc,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_explain(exc)
        ) from exc

    logger.info(
        "credential probe ok in %d ms | endpoint=%s deployment=%s creds=%s",
        round((time.perf_counter() - started) * 1000),
        credentials.endpoint, credentials.deployment, credentials.fingerprint,
    )


def _explain(exc: Exception) -> str:
    """Turn an Azure/OpenAI SDK error into something worth showing on a form."""
    name = type(exc).__name__
    text = str(exc)

    if name == "AuthenticationError" or "401" in text:
        return "Azure rejected that API key. Check the key and the resource it belongs to."

    if name == "NotFoundError" or "DeploymentNotFound" in text or "404" in text:
        return (
            "That deployment was not found on this endpoint. Check the deployment "
            "name and the API version."
        )

    if name == "PermissionDeniedError" or "403" in text:
        return "That key is not permitted to use this deployment."

    if name in {"APIConnectionError", "APITimeoutError"} or "getaddrinfo" in text:
        return "Could not reach that Azure endpoint. Check the URL and your network."

    if name == "RateLimitError" or "429" in text:
        return "Azure is rate limiting this resource right now. Try again in a moment."

    if name == "BadRequestError" or "400" in text:
        return f"Azure rejected the request: {text[:200]}"

    logger.debug("unmapped probe error %s: %s", name, text)
    return f"Could not verify those credentials ({name})."


@router.post("/login")
def login(body: LoginRequest) -> dict:
    logger.info(
        "POST /auth/login | endpoint=%s deployment=%s api_version=%s",
        body.endpoint, body.deployment, body.api_version,
    )

    try:
        credentials = AzureCredentials.build(
            endpoint=body.endpoint,
            api_key=body.api_key,
            deployment=body.deployment,
            api_version=body.api_version,
            simple_deployment=body.simple_deployment,
        )
    except ValueError as exc:
        logger.info("login rejected before probing: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    _probe(credentials)

    session = session_store.create(credentials)
    return {
        "authenticated": True,
        "ttl_seconds": session_store.ttl_seconds,
        **session.public(session_store.ttl_seconds),
    }


@router.post("/logout")
def logout(x_session_id: str | None = Header(default=None)) -> dict:
    session = session_store.delete(x_session_id)

    if session is not None and not session_store.fingerprint_in_use(
        session.credentials.fingerprint
    ):
        forget_models(session.credentials.fingerprint)

    return {"authenticated": False, "closed": session is not None}


@router.get("/session")
def read_session(x_session_id: str | None = Header(default=None)) -> dict:
    """Whether this session id is still live, and what it is pointed at.

    The frontend calls this on boot so a persisted sign-in that the backend has
    forgotten (restart, idle expiry) lands the user back on the login page
    instead of failing on their first generation.
    """
    session = session_store.get(x_session_id)

    if session is None:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "ttl_seconds": session_store.ttl_seconds,
        **session.public(session_store.ttl_seconds),
    }


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not signed in. Enter your Azure credentials to continue.",
        headers={"WWW-Authenticate": SESSION_HEADER},
    )


async def require_credentials(
    x_session_id: str | None = Header(default=None),
) -> AsyncIterator[AzureCredentials]:
    """Resolve the session and bind its credentials to this request's context.

    An ``async`` generator on purpose: FastAPI runs it in the request's own task,
    so the ContextVar set here is visible to the endpoint — including sync
    endpoints, which Starlette dispatches to a worker thread with a copy of this
    context — and to every LangGraph branch underneath it. A ``BaseHTTPMiddleware``
    would run in a different task and the value would not survive.
    """
    session: Session | None = session_store.get(x_session_id)

    if session is None:
        raise _unauthorized()

    token = set_credentials(session.credentials)
    try:
        yield session.credentials
    finally:
        reset_credentials(token)
