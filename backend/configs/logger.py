import logging
import os
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "run.log"

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

NOISY_LIBRARIES = (
    "urllib3",
    "openai",
    "httpx",
    "httpcore",
    "watchfiles",
    "watchfiles.main",
    "langchain",
    "langchain_core",
    "asyncio",
)


def _default_level() -> int:
    name = os.getenv("LOG_LEVEL", "INFO").upper()
    return getattr(logging, name, logging.INFO)


def setup_logging(level: int | None = None) -> None:
    resolved = level if level is not None else _default_level()

    logging.basicConfig(
        level=resolved,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
        ],
        force=True,
    )

    for name in NOISY_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.getLogger(__name__).debug(
        "logging configured: level=%s file=%s", logging.getLevelName(resolved), LOG_FILE
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def preview(text: str, limit: int = 120) -> str:
    if not text:
        return "<empty>"
    flattened = " ".join(str(text).split())
    if len(flattened) <= limit:
        return flattened
    return flattened[:limit] + f"... (+{len(flattened) - limit} chars)"


setup_logging()

logger = get_logger("studio")
