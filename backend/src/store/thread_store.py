import json
import sqlite3
import time

from configs.database import init_thread_index, write_lock
from configs.logger import get_logger, preview

logger = get_logger(__name__)

MAX_TITLE_CHARS = 60


class ThreadStore:

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        init_thread_index(conn)


    @staticmethod
    def title_from(query: str) -> str:
        clean = " ".join((query or "").split())
        if not clean:
            return "Untitled thread"
        if len(clean) <= MAX_TITLE_CHARS:
            return clean
        return clean[:MAX_TITLE_CHARS].rstrip() + "…"

    def record(self, thread_id: str, query: str) -> None:
        now = time.time()
        title = self.title_from(query)

        with write_lock:
            self.conn.execute(
                """
                INSERT INTO threads (id, title, created_at, updated_at, messages)
                VALUES (?, ?, ?, ?, '[]')
                ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (thread_id, title, now, now),
            )
            self.conn.commit()

        logger.info("indexed thread %s | title=%r", thread_id, title)

    def touch(self, thread_id: str) -> None:
        with write_lock:
            cur = self.conn.execute(
                "UPDATE threads SET updated_at = ? WHERE id = ?",
                (time.time(), thread_id),
            )
            self.conn.commit()

        if cur.rowcount == 0:
            logger.warning(
                "touch called for thread %s, which is not in the index — "
                "it will not appear in the thread list", thread_id,
            )
        else:
            logger.debug("bumped updated_at for thread %s", thread_id)

    def append_messages(self, thread_id: str, new_messages: list[dict]) -> None:
        if not new_messages:
            return

        with write_lock:
            row = self.conn.execute(
                "SELECT messages FROM threads WHERE id = ?", (thread_id,)
            ).fetchone()

            if row is None:
                logger.warning(
                    "cannot append %d message(s): thread %s is not in the index",
                    len(new_messages), thread_id,
                )
                return

            try:
                existing = json.loads(row["messages"])
            except json.JSONDecodeError:
                logger.exception(
                    "thread %s has unreadable messages JSON; starting a fresh transcript",
                    thread_id,
                )
                existing = []

            combined = existing + new_messages
            self.conn.execute(
                "UPDATE threads SET messages = ?, updated_at = ? WHERE id = ?",
                (json.dumps(combined), time.time(), thread_id),
            )
            self.conn.commit()

        logger.debug(
            "appended %d message(s) to thread %s (now %d total)",
            len(new_messages), thread_id, len(combined),
        )

    def delete(self, thread_id: str) -> bool:
        with write_lock:
            cur = self.conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
            self.conn.commit()

        removed = cur.rowcount > 0
        logger.info(
            "delete thread %s from index: %s",
            thread_id, "removed" if removed else "not found",
        )
        return removed


    def list_all(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT id, title, created_at, updated_at, messages
            FROM threads
            ORDER BY updated_at DESC
            """
        ).fetchall()

        threads = [
            {
                "thread_id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "message_count": len(self._messages(row)),
            }
            for row in rows
        ]

        logger.info("listing %d thread(s) from the index", len(threads))
        return threads

    def messages(self, thread_id: str) -> list[dict]:
        row = self.conn.execute(
            "SELECT messages FROM threads WHERE id = ?", (thread_id,)
        ).fetchone()

        if row is None:
            logger.debug("no index row for thread %s; no transcript to return", thread_id)
            return []

        return self._messages(row)

    def exists(self, thread_id: str) -> bool:
        found = self.conn.execute(
            "SELECT 1 FROM threads WHERE id = ?", (thread_id,)
        ).fetchone() is not None
        logger.debug("thread %s in index: %s", thread_id, found)
        return found

    @staticmethod
    def _messages(row: sqlite3.Row) -> list[dict]:
        try:
            return json.loads(row["messages"])
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "unreadable messages JSON in the index (%s); treating as empty",
                preview(row["messages"], limit=80),
            )
            return []
