import time

import pytest

from configs.credentials import AzureCredentials
from src.store.session_store import SessionStore


def creds(api_key="test-key", deployment="gpt-4o-mini"):
    return AzureCredentials.build(
        endpoint="https://test.openai.azure.com",
        api_key=api_key,
        deployment=deployment,
    )


@pytest.fixture
def store():
    return SessionStore(ttl_seconds=60)


def test_create_returns_a_live_session(store):
    session = store.create(creds())

    assert session.session_id
    assert store.get(session.session_id) is session
    assert len(store) == 1


def test_session_ids_are_unguessable_and_distinct(store):
    first = store.create(creds()).session_id
    second = store.create(creds()).session_id

    assert first != second
    assert len(first) >= 32


def test_get_returns_none_for_an_unknown_or_missing_id(store):
    assert store.get("nope") is None
    assert store.get(None) is None
    assert store.get("") is None


def test_the_session_holds_the_credentials_it_was_given(store):
    session = store.create(creds(api_key="secret", deployment="gpt-4o"))

    assert store.get(session.session_id).credentials.api_key == "secret"
    assert store.get(session.session_id).credentials.deployment == "gpt-4o"


def test_public_never_exposes_the_api_key(store):
    session = store.create(creds(api_key="super-secret"))

    body = session.public(store.ttl_seconds)

    assert "super-secret" not in str(body)
    assert "api_key" not in body
    assert body["session_id"] == session.session_id
    assert body["expires_at"] > body["created_at"]


def test_delete_removes_the_session(store):
    session = store.create(creds())

    assert store.delete(session.session_id) is session
    assert store.get(session.session_id) is None
    assert len(store) == 0


def test_deleting_twice_is_not_an_error(store):
    session = store.create(creds())
    store.delete(session.session_id)

    assert store.delete(session.session_id) is None


def test_an_idle_session_expires(store):
    store.ttl_seconds = 0.05
    session = store.create(creds())

    time.sleep(0.1)

    assert store.get(session.session_id) is None
    assert len(store) == 0


def test_activity_slides_the_expiry_forward(store):
    store.ttl_seconds = 0.2
    session = store.create(creds())

    for _ in range(3):
        time.sleep(0.1)
        assert store.get(session.session_id) is not None


def test_purge_expired_reports_what_it_dropped(store):
    store.ttl_seconds = 0.05
    store.create(creds())
    store.create(creds(api_key="another"))

    time.sleep(0.1)

    assert store.purge_expired() == 2
    assert len(store) == 0


def test_fingerprint_in_use_tracks_the_last_session_out(store):
    shared = creds()
    first = store.create(shared)
    second = store.create(shared)

    store.delete(first.session_id)
    assert store.fingerprint_in_use(shared.fingerprint) is True

    store.delete(second.session_id)
    assert store.fingerprint_in_use(shared.fingerprint) is False


def test_two_users_get_independent_sessions(store):
    mine = store.create(creds(api_key="mine"))
    yours = store.create(creds(api_key="yours"))

    assert store.get(mine.session_id).credentials.api_key == "mine"
    assert store.get(yours.session_id).credentials.api_key == "yours"

    store.delete(mine.session_id)
    assert store.get(yours.session_id) is not None


def test_clear_drops_everything(store):
    store.create(creds())
    store.create(creds(api_key="another"))

    store.clear()

    assert len(store) == 0
