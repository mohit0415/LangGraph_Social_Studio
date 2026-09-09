import json
import time

import pytest

from src.store.thread_store import MAX_TITLE_CHARS, ThreadStore


def test_title_from_keeps_a_short_query_intact(store):
    assert store.title_from("Shipping daily") == "Shipping daily"


def test_title_from_collapses_whitespace(store):
    assert store.title_from("  a\n\n  b\tc  ") == "a b c"


@pytest.mark.parametrize("query", ["", "   ", "\n\t", None])
def test_title_from_falls_back_for_an_empty_query(store, query):
    assert store.title_from(query) == "Untitled thread"


def test_title_from_truncates_with_an_ellipsis(store):
    title = store.title_from("word " * 100)

    assert title.endswith("…")
    assert len(title) <= MAX_TITLE_CHARS + 1


def test_title_from_keeps_a_query_exactly_at_the_limit(store):
    exact = "a" * MAX_TITLE_CHARS

    assert store.title_from(exact) == exact


def test_record_then_exists(store):
    store.record("t1", "Shipping daily reduces incidents")

    assert store.exists("t1") is True
    assert store.exists("nope") is False


def test_record_stores_the_title_and_timestamps(store):
    before = time.time()
    store.record("t1", "Shipping daily")

    row = store.list_all()[0]

    assert row["thread_id"] == "t1"
    assert row["title"] == "Shipping daily"
    assert row["created_at"] >= before
    assert row["updated_at"] >= before


def test_record_is_idempotent_and_bumps_updated_at(store):
    store.record("t1", "first")
    first = store.list_all()[0]

    time.sleep(0.01)
    store.record("t1", "second")
    second = store.list_all()[0]

    assert len(store.list_all()) == 1
    assert second["title"] == "first"
    assert second["created_at"] == first["created_at"]
    assert second["updated_at"] > first["updated_at"]


def test_touch_bumps_updated_at(store):
    store.record("t1", "first")
    before = store.list_all()[0]["updated_at"]

    time.sleep(0.01)
    store.touch("t1")

    assert store.list_all()[0]["updated_at"] > before


def test_touch_on_an_unknown_thread_is_a_no_op(store):
    store.touch("ghost")

    assert store.list_all() == []


def test_append_messages_accumulates(store):
    store.record("t1", "q")
    store.append_messages("t1", [{"role": "user", "text": "one"}])
    store.append_messages("t1", [{"role": "system", "text": "two"}])

    messages = store.messages("t1")

    assert [m["text"] for m in messages] == ["one", "two"]
    assert [m["role"] for m in messages] == ["user", "system"]


def test_append_messages_ignores_an_empty_list(store):
    store.record("t1", "q")
    store.append_messages("t1", [])

    assert store.messages("t1") == []


def test_append_messages_on_an_unknown_thread_does_not_raise(store):
    store.append_messages("ghost", [{"role": "user", "text": "hi"}])

    assert store.messages("ghost") == []


def test_append_messages_bumps_updated_at(store):
    store.record("t1", "q")
    before = store.list_all()[0]["updated_at"]

    time.sleep(0.01)
    store.append_messages("t1", [{"role": "user", "text": "hi"}])

    assert store.list_all()[0]["updated_at"] > before


def test_messages_for_an_unknown_thread_is_empty(store):
    assert store.messages("ghost") == []


def test_unreadable_messages_json_is_treated_as_empty(store, memory_conn):
    store.record("t1", "q")
    memory_conn.execute("UPDATE threads SET messages = ? WHERE id = ?", ("{oops", "t1"))
    memory_conn.commit()

    assert store.messages("t1") == []
    assert store.list_all()[0]["message_count"] == 0


def test_append_recovers_from_unreadable_json(store, memory_conn):
    store.record("t1", "q")
    memory_conn.execute("UPDATE threads SET messages = ? WHERE id = ?", ("{oops", "t1"))
    memory_conn.commit()

    store.append_messages("t1", [{"role": "user", "text": "fresh"}])

    assert store.messages("t1") == [{"role": "user", "text": "fresh"}]


def test_list_all_is_newest_first(store):
    store.record("old", "first")
    time.sleep(0.01)
    store.record("new", "second")

    assert [row["thread_id"] for row in store.list_all()] == ["new", "old"]


def test_list_all_reports_the_message_count(store):
    store.record("t1", "q")
    store.append_messages("t1", [{"role": "user", "text": "a"}, {"role": "system", "text": "b"}])

    assert store.list_all()[0]["message_count"] == 2


def test_list_all_is_empty_on_a_fresh_database(store):
    assert store.list_all() == []


def test_delete_removes_the_row_and_reports_it(store):
    store.record("t1", "q")

    assert store.delete("t1") is True
    assert store.exists("t1") is False
    assert store.list_all() == []


def test_delete_on_an_unknown_thread_reports_false(store):
    assert store.delete("ghost") is False


def test_schema_is_created_on_construction(memory_conn):
    ThreadStore(memory_conn)

    tables = {
        row[0]
        for row in memory_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    indexes = {
        row[0]
        for row in memory_conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }

    assert "threads" in tables
    assert "threads_updated_at" in indexes


def test_constructing_twice_does_not_wipe_existing_rows(memory_conn):
    first = ThreadStore(memory_conn)
    first.record("t1", "q")

    second = ThreadStore(memory_conn)

    assert second.exists("t1") is True


def test_messages_column_holds_valid_json(store, memory_conn):
    store.record("t1", "q")
    store.append_messages("t1", [{"role": "user", "text": "hi"}])

    raw = memory_conn.execute("SELECT messages FROM threads WHERE id = 't1'").fetchone()[0]

    assert json.loads(raw) == [{"role": "user", "text": "hi"}]
