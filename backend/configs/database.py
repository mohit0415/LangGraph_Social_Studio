import os
import sqlite3
import threading
from pathlib import Path

from configs.logger import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_DB_PATH = DATA_DIR / "studio.db"


def db_path() -> Path:
    override = os.getenv("STUDIO_DB_PATH")
    path = Path(override) if override else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect(label: str) -> sqlite3.Connection:
    path = db_path()
    logger.info("opening SQLite connection %r -> %s", label, path)

    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.commit()

    logger.debug(
        "connection %r ready | journal_mode=%s busy_timeout=5000ms",
        label, conn.execute("PRAGMA journal_mode").fetchone()[0],
    )
    return conn


THREAD_SCHEMA = """
CREATE TABLE IF NOT EXISTS threads (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL,
    messages    TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS threads_updated_at
    ON threads (updated_at DESC);
"""

write_lock = threading.Lock()


def init_thread_index(conn: sqlite3.Connection) -> None:
    with write_lock:
        conn.executescript(THREAD_SCHEMA)
        conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM threads").fetchone()[0]
    logger.info("thread index ready at %s | %d existing thread(s)", db_path(), count)
