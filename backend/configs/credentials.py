"""Request-scoped Azure OpenAI credentials.

The backend deliberately holds no Azure credentials of its own. Nothing in this
module — or in ``configs.llms`` — reads ``AZURE_OPENAI_*`` out of the process
environment or a ``.env`` file. Every LLM client is built from the credentials
the signed-in user typed on the login page, which live in an in-memory session
(see ``src.store.session_store``) and are pushed into a ``ContextVar`` for the
duration of one request.

The ContextVar is what lets the credentials reach code that never sees the HTTP
request: ``src.agent.ask`` calls ``configs.llms.model_for`` several frames deep
inside the compiled LangGraph, and the platform branches run in parallel worker
threads. LangGraph submits those branches with ``copy_context().run(...)``, so a
value set here on the request thread is visible in every branch, without
threading a credentials argument through every node signature.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Iterator

from configs.logger import get_logger

logger = get_logger(__name__)

DEFAULT_API_VERSION = "2024-12-01-preview"


class MissingCredentialsError(RuntimeError):
    """Raised when an LLM is requested outside an authenticated request."""


@dataclass(frozen=True, slots=True)
class AzureCredentials:
    """One user's Azure OpenAI connection details.

    Frozen so it can be used as a cache key and cannot be mutated once a session
    holds it. ``simple_deployment`` is optional: when set, the cheap tier routes
    to it and the complex tier keeps using ``deployment``; when blank, both tiers
    share ``deployment``.
    """

    endpoint: str
    api_key: str
    deployment: str
    api_version: str = DEFAULT_API_VERSION
    simple_deployment: str = ""

    @staticmethod
    def _clean(value: str | None) -> str:
        return (value or "").strip()

    @classmethod
    def build(
        cls,
        endpoint: str,
        api_key: str,
        deployment: str,
        api_version: str = DEFAULT_API_VERSION,
        simple_deployment: str = "",
    ) -> "AzureCredentials":
        """Normalise and validate the four required fields.

        Raises ``ValueError`` naming the first field that is missing or
        malformed, which the login route turns into a 400 the user can act on.
        """
        endpoint = cls._clean(endpoint).rstrip("/")
        api_key = cls._clean(api_key)
        deployment = cls._clean(deployment)
        api_version = cls._clean(api_version) or DEFAULT_API_VERSION
        simple_deployment = cls._clean(simple_deployment)

        if not endpoint:
            raise ValueError("Azure endpoint is required.")
        if not endpoint.startswith(("http://", "https://")):
            raise ValueError(
                "Azure endpoint must be a full URL, e.g. "
                "https://your-resource.openai.azure.com"
            )
        if not api_key:
            raise ValueError("Azure API key is required.")
        if not deployment:
            raise ValueError("Azure deployment name is required.")

        return cls(
            endpoint=endpoint + "/",
            api_key=api_key,
            deployment=deployment,
            api_version=api_version,
            simple_deployment=simple_deployment,
        )

    def deployment_for(self, tier: str) -> str:
        """The deployment this tier should call."""
        if tier == "simple" and self.simple_deployment:
            return self.simple_deployment
        return self.deployment

    @property
    def fingerprint(self) -> str:
        """Short stable id for this credential set.

        Used as a cache key and in logs so two sessions can be told apart
        without the API key ever appearing anywhere it might be written down.
        """
        raw = "|".join(
            [
                self.endpoint,
                self.api_key,
                self.deployment,
                self.api_version,
                self.simple_deployment,
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def public(self) -> dict:
        """Everything about this credential set that is safe to send back.

        The API key is never included — not in responses, not in logs.
        """
        return {
            "endpoint": self.endpoint,
            "deployment": self.deployment,
            "api_version": self.api_version,
            "simple_deployment": self.simple_deployment,
            "fingerprint": self.fingerprint,
        }

    def __repr__(self) -> str:  # pragma: no cover - defensive, keeps keys out of tracebacks
        return (
            f"AzureCredentials(endpoint={self.endpoint!r}, "
            f"deployment={self.deployment!r}, api_version={self.api_version!r}, "
            f"api_key='***', fingerprint={self.fingerprint!r})"
        )


_current: ContextVar[AzureCredentials | None] = ContextVar(
    "azure_credentials", default=None
)


def set_credentials(credentials: AzureCredentials | None) -> Token:
    """Bind credentials to the current context. Returns a token for ``reset``."""
    return _current.set(credentials)


def reset_credentials(token: Token) -> None:
    _current.reset(token)


@contextmanager
def use_credentials(credentials: AzureCredentials) -> Iterator[AzureCredentials]:
    """Run a block with these credentials bound to the current context."""
    token = set_credentials(credentials)
    try:
        yield credentials
    finally:
        reset_credentials(token)


def has_credentials() -> bool:
    return _current.get() is not None


def current_credentials() -> AzureCredentials:
    """The credentials for the request in flight.

    Raises ``MissingCredentialsError`` rather than falling back to anything from
    the environment: an LLM call with no signed-in user is a bug, and silently
    reaching for a server-side key is exactly what this design removes.
    """
    credentials = _current.get()
    if credentials is None:
        logger.error(
            "an LLM was requested with no credentials bound to this context — the "
            "call reached configs.llms outside an authenticated request, or the "
            "route is missing the require_credentials dependency"
        )
        raise MissingCredentialsError(
            "No Azure credentials for this request. Sign in again."
        )
    return credentials
