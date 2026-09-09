"""In-memory store of signed-in sessions and the Azure credentials behind them.

Deliberately in memory only. The API key a user types on the login page is never
written to SQLite, never logged, and never returned to the browser — the browser
only ever holds the opaque session id this store hands out. A backend restart
drops every session, which is the intended trade: the keys go with it and users
sign in again.
"""

from __future__ import annotations

import secrets
import threading
import time
from dataclasses import dataclass

from configs.credentials import AzureCredentials
from configs.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TTL_SECONDS = 8 * 60 * 60


@dataclass
class Session:
    session_id: str
    credentials: AzureCredentials
    created_at: float
    last_seen_at: float

    def public(self, ttl_seconds: float) -> dict:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "expires_at": self.last_seen_at + ttl_seconds,
            **self.credentials.public(),
        }


class SessionStore:

    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        logger.info(
            "session store ready | in-memory only, %d hour idle TTL — Azure keys "
            "live here and nowhere else",
            round(ttl_seconds / 3600),
        )

    def create(self, credentials: AzureCredentials) -> Session:
        now = time.time()
        session = Session(
            session_id=secrets.token_urlsafe(32),
            credentials=credentials,
            created_at=now,
            last_seen_at=now,
        )

        with self._lock:
            self._sessions[session.session_id] = session
            live = len(self._sessions)

        logger.info(
            "session opened | creds=%s deployment=%s | %d live session(s)",
            credentials.fingerprint, credentials.deployment, live,
        )
        return session

    def get(self, session_id: str | None) -> Session | None:
        """Look up a live session, sliding its idle expiry forward."""
        if not session_id:
            return None

        now = time.time()
        with self._lock:
            session = self._sessions.get(session_id)

            if session is None:
                logger.debug("session lookup miss for %s...", session_id[:8])
                return None

            if now - session.last_seen_at > self.ttl_seconds:
                self._sessions.pop(session_id, None)
                logger.info(
                    "session expired after %d min idle | creds=%s",
                    round((now - session.last_seen_at) / 60),
                    session.credentials.fingerprint,
                )
                return None

            session.last_seen_at = now
            return session

    def delete(self, session_id: str | None) -> Session | None:
        if not session_id:
            return None

        with self._lock:
            session = self._sessions.pop(session_id, None)

        if session is None:
            logger.debug("logout for an unknown or already-closed session")
            return None

        logger.info(
            "session closed | creds=%s after %d min",
            session.credentials.fingerprint,
            round((time.time() - session.created_at) / 60),
        )
        return session

    def fingerprint_in_use(self, fingerprint: str) -> bool:
        """Whether any other live session still uses these credentials.

        Logout clears the cached LLM clients built from a credential set, but
        only once no other session is still signed in with the same ones.
        """
        with self._lock:
            return any(
                s.credentials.fingerprint == fingerprint for s in self._sessions.values()
            )

    def purge_expired(self) -> int:
        now = time.time()
        with self._lock:
            stale = [
                sid
                for sid, s in self._sessions.items()
                if now - s.last_seen_at > self.ttl_seconds
            ]
            for sid in stale:
                self._sessions.pop(sid, None)

        if stale:
            logger.info("purged %d expired session(s)", len(stale))
        return len(stale)

    def clear(self) -> None:
        with self._lock:
            count = len(self._sessions)
            self._sessions.clear()
        if count:
            logger.info("cleared %d session(s)", count)

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)
