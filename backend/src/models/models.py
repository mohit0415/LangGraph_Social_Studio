from pydantic import BaseModel, field_validator

from configs.logger import get_logger, preview

logger = get_logger(__name__)


class SocialInput(BaseModel):

    query: str
    thread_id: str | None = None

    @field_validator("query")
    @classmethod
    def _log_query(cls, value: str) -> str:
        stripped = (value or "").strip()

        if not stripped:
            logger.warning("received an EMPTY query — the brief will have no source material")
        elif len(stripped) < 20:
            logger.warning(
                "received a very short query (%d chars): %r — the posts will be thin",
                len(stripped), stripped,
            )
        else:
            logger.debug("accepted query of %d chars: %s", len(stripped), preview(stripped))

        return value

    @field_validator("thread_id")
    @classmethod
    def _log_thread(cls, value: str | None) -> str | None:
        logger.debug(
            "request targets %s",
            f"existing thread {value}" if value else "a new thread",
        )
        return value
