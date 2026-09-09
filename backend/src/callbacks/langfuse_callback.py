from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from configs.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

try:
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    _IMPORT_ERROR: Optional[Exception] = None
except Exception as exc:
    Langfuse = None
    CallbackHandler = None
    _IMPORT_ERROR = exc
    logger.warning("langfuse is not importable (%s); tracing is disabled", exc)


DEFAULT_HOST = "https://cloud.langfuse.com"


class LangfuseCallbackManager:

    def __init__(
        self,
        public_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        host: Optional[str] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        self.public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
        self.secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
        self.host = host or os.getenv("LANGFUSE_HOST") or DEFAULT_HOST

        self.session_id = session_id
        self.user_id = user_id

        self._client: Optional[Any] = None
        self._handler: Optional[Any] = None
        self._warned = False

        if not self.enabled:
            logger.warning(
                "Langfuse disabled: set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY "
                "in .env to turn tracing on (host=%s)",
                self.host,
            )
        else:
            logger.info("Langfuse configured | host=%s", self.host)

    @property
    def enabled(self) -> bool:
        return bool(CallbackHandler and self.public_key and self.secret_key)

    def get_client(self) -> Optional[Any]:
        if not self.enabled:
            return None

        if self._client is None:
            os.environ["LANGFUSE_PUBLIC_KEY"] = self.public_key
            os.environ["LANGFUSE_SECRET_KEY"] = self.secret_key
            os.environ["LANGFUSE_HOST"] = self.host

            try:
                self._client = Langfuse(
                    public_key=self.public_key,
                    secret_key=self.secret_key,
                    host=self.host,
                )
            except Exception:
                logger.exception("could not create the Langfuse client; tracing is off")
                self._client = None
                return None

            try:
                if not self._client.auth_check():
                    logger.warning(
                        "Langfuse auth_check() failed — keys or host look wrong; "
                        "runs may not show up at %s",
                        self.host,
                    )
            except Exception as exc:
                logger.warning("Langfuse auth_check() could not run (%s); continuing", exc)

        return self._client

    def get_callback_handler(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        trace_name: Optional[str] = None,
    ) -> Optional[Any]:
        if not self.enabled:
            if not self._warned:
                logger.info("skipping Langfuse handler: tracing is disabled")
                self._warned = True
            return None

        if session_id:
            self.session_id = session_id
        if user_id:
            self.user_id = user_id

        if self._handler is None:
            if self.get_client() is None:
                return None
            try:
                self._handler = CallbackHandler(
                    public_key=self.public_key,
                    update_trace=True,
                )
                logger.info("Langfuse CallbackHandler ready (trace_name=%s)", trace_name)
            except Exception:
                logger.exception("could not create the Langfuse CallbackHandler")
                return None

        return self._handler

    def build_run_config(
        self,
        thread_id: str,
        trace_name: str = "ask",
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Optional[Any]]:
        config: Dict[str, Any] = {"configurable": {"thread_id": thread_id}}

        handler = self.get_callback_handler(session_id=thread_id, user_id=user_id)
        if handler is None:
            return config, None

        metadata: Dict[str, Any] = {
            "langfuse_session_id": thread_id,
            "langfuse_tags": list(tags or [trace_name]),
            "thread_id": thread_id,
        }
        effective_user = user_id or self.user_id
        if effective_user:
            metadata["langfuse_user_id"] = effective_user
        if extra_metadata:
            metadata.update(extra_metadata)

        config["callbacks"] = [handler]
        config["metadata"] = metadata
        config["run_name"] = trace_name

        logger.debug(
            "langfuse config | thread_id=%s session_id=%s trace_name=%s tags=%s",
            thread_id, thread_id, trace_name, metadata["langfuse_tags"],
        )
        return config, handler

    def flush(self) -> None:
        client = self._client
        if client is None:
            return
        try:
            client.flush()
            logger.debug("flushed pending Langfuse traces")
        except Exception:
            logger.exception("flushing Langfuse traces failed (ignored)")

    def shutdown(self) -> None:
        client = self._client
        if client is None:
            return
        try:
            client.shutdown()
            logger.info("Langfuse client shut down cleanly")
        except Exception:
            self.flush()


_langfuse_manager: Optional[LangfuseCallbackManager] = None


def get_langfuse_manager() -> LangfuseCallbackManager:
    global _langfuse_manager
    if _langfuse_manager is None:
        _langfuse_manager = LangfuseCallbackManager()
    return _langfuse_manager


def build_run_config(
    thread_id: str,
    trace_name: str = "ask",
    user_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Optional[Any]]:
    return get_langfuse_manager().build_run_config(
        thread_id,
        trace_name=trace_name,
        user_id=user_id,
        tags=tags,
        extra_metadata=extra_metadata,
    )


def flush_langfuse() -> None:
    get_langfuse_manager().flush()


__all__ = [
    "LangfuseCallbackManager",
    "get_langfuse_manager",
    "build_run_config",
    "flush_langfuse",
]
