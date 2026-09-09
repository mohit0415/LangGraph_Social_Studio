from configs.logger import get_logger
from src.agent import write_post as _write_post

logger = get_logger(__name__)

__all__ = ["write_post"]


def write_post(platform: str, brief: str, fix: str = "", old_draft: str = "") -> str:
    logger.warning(
        "DEPRECATED: src.utils.write_post.write_post was called for platform=%r. "
        "Import `from src.agent import write_post` instead — this shim only "
        "delegates and will be removed.",
        platform,
    )
    return _write_post(platform, brief, fix=fix, old_draft=old_draft)
