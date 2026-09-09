"""The credential path end to end: login, guarded routes, logout."""

import pytest
from fastapi import HTTPException

import src.routes.auth as auth

GOOD = {
    "endpoint": "https://test.openai.azure.com",
    "api_key": "test-key",
    "deployment": "gpt-4o-mini",
    "api_version": "2024-02-01",
}

HEADER = auth.SESSION_HEADER


@pytest.fixture
def no_probe(monkeypatch):
    """Accept any credentials without calling Azure."""
    monkeypatch.setattr(auth, "_probe", lambda credentials: None)


@pytest.fixture
def rejecting_probe(monkeypatch):
    def reject(credentials):
        raise HTTPException(status_code=401, detail="Azure rejected that API key.")

    monkeypatch.setattr(auth, "_probe", reject)


@pytest.fixture
def signed_in(raw_client, no_probe):
    body = raw_client.post("/auth/login", json=GOOD).json()
    yield body
    auth.session_store.delete(body["session_id"])


# --- login ------------------------------------------------------------------


def test_login_returns_a_session_id(signed_in):
    assert signed_in["authenticated"] is True
    assert signed_in["session_id"]
    assert signed_in["deployment"] == "gpt-4o-mini"


def test_login_never_echoes_the_api_key(signed_in):
    assert "api_key" not in signed_in
    assert "test-key" not in str(signed_in)


def test_login_rejects_bad_credentials_with_a_readable_message(
    raw_client, rejecting_probe
):
    response = raw_client.post("/auth/login", json=GOOD)

    assert response.status_code == 401
    assert "rejected" in response.json()["detail"]


@pytest.mark.parametrize(
    "field, value, expected",
    [
        ("endpoint", "", "endpoint is required"),
        ("endpoint", "test.openai.azure.com", "full URL"),
        ("api_key", "   ", "API key is required"),
        ("deployment", "", "deployment name is required"),
    ],
)
def test_login_validates_the_fields_before_calling_azure(
    raw_client, no_probe, field, value, expected
):
    response = raw_client.post("/auth/login", json={**GOOD, field: value})

    assert response.status_code == 400
    assert expected in response.json()["detail"]


def test_login_requires_the_credential_fields(raw_client, no_probe):
    assert raw_client.post("/auth/login", json={}).status_code == 422


def test_login_defaults_the_api_version(raw_client, no_probe):
    payload = {k: v for k, v in GOOD.items() if k != "api_version"}

    body = raw_client.post("/auth/login", json=payload).json()

    assert body["api_version"] == auth.DEFAULT_API_VERSION
    auth.session_store.delete(body["session_id"])


def test_login_carries_an_optional_simple_deployment(raw_client, no_probe):
    body = raw_client.post(
        "/auth/login", json={**GOOD, "simple_deployment": "gpt-35-turbo"}
    ).json()

    assert body["simple_deployment"] == "gpt-35-turbo"
    auth.session_store.delete(body["session_id"])


# --- the guard --------------------------------------------------------------


@pytest.mark.parametrize(
    "method, path",
    [
        ("post", "/ask"),
        ("get", "/threads"),
        ("get", "/threads/anything"),
        ("delete", "/threads/anything"),
    ],
)
def test_guarded_routes_refuse_an_unsigned_request(raw_client, method, path):
    call = getattr(raw_client, method)
    response = call(path, json={"query": "hello"}) if method == "post" else call(path)

    assert response.status_code == 401
    assert "sign" in response.json()["detail"].lower()


def test_a_forged_session_id_is_refused(raw_client):
    response = raw_client.get("/threads", headers={HEADER: "not-a-real-session"})

    assert response.status_code == 401


@pytest.mark.parametrize("path", ["/platforms", "/health"])
def test_public_routes_stay_open(raw_client, path):
    assert raw_client.get(path).status_code == 200


def test_a_signed_in_request_is_allowed_through(raw_client, signed_in):
    response = raw_client.get(
        "/threads", headers={HEADER: signed_in["session_id"]}
    )

    assert response.status_code == 200


# --- session and logout -----------------------------------------------------


def test_session_reports_a_live_session(raw_client, signed_in):
    body = raw_client.get(
        "/auth/session", headers={HEADER: signed_in["session_id"]}
    ).json()

    assert body["authenticated"] is True
    assert body["deployment"] == "gpt-4o-mini"
    assert "test-key" not in str(body)


def test_session_reports_no_session_without_a_header(raw_client):
    assert raw_client.get("/auth/session").json() == {"authenticated": False}


def test_logout_closes_the_session(raw_client, no_probe):
    session_id = raw_client.post("/auth/login", json=GOOD).json()["session_id"]

    body = raw_client.post("/auth/logout", headers={HEADER: session_id}).json()

    assert body == {"authenticated": False, "closed": True}
    assert (
        raw_client.get("/auth/session", headers={HEADER: session_id}).json()[
            "authenticated"
        ]
        is False
    )


def test_a_closed_session_can_no_longer_reach_the_studio(raw_client, no_probe):
    session_id = raw_client.post("/auth/login", json=GOOD).json()["session_id"]
    raw_client.post("/auth/logout", headers={HEADER: session_id})

    assert raw_client.get("/threads", headers={HEADER: session_id}).status_code == 401


def test_logout_without_a_session_is_not_an_error(raw_client):
    assert raw_client.post("/auth/logout").json() == {
        "authenticated": False,
        "closed": False,
    }


def test_logout_drops_the_cached_clients_for_those_credentials(
    raw_client, no_probe, monkeypatch
):
    forgotten = []
    monkeypatch.setattr(auth, "forget_models", lambda fp: forgotten.append(fp))

    session_id = raw_client.post("/auth/login", json=GOOD).json()["session_id"]
    raw_client.post("/auth/logout", headers={HEADER: session_id})

    assert len(forgotten) == 1


def test_logout_keeps_the_clients_another_session_still_needs(
    raw_client, no_probe, monkeypatch
):
    forgotten = []
    monkeypatch.setattr(auth, "forget_models", lambda fp: forgotten.append(fp))

    first = raw_client.post("/auth/login", json=GOOD).json()["session_id"]
    second = raw_client.post("/auth/login", json=GOOD).json()["session_id"]

    raw_client.post("/auth/logout", headers={HEADER: first})
    assert forgotten == []

    raw_client.post("/auth/logout", headers={HEADER: second})
    assert len(forgotten) == 1


# --- the credentials actually reach the model layer -------------------------


def test_the_signed_in_credentials_are_bound_for_the_request(
    raw_client, signed_in, studio, monkeypatch
):
    """/ask should run with the login credentials on the context, not the env."""
    from configs.credentials import current_credentials

    seen = {}
    real_ask = studio.ask

    def record(system, user, task="write", routing_text="", **kwargs):
        seen.setdefault("deployment", current_credentials().deployment)
        return real_ask(system, user, task=task, routing_text=routing_text, **kwargs)

    monkeypatch.setattr("src.agent.ask", record)

    response = raw_client.post(
        "/ask",
        json={"query": "A study of 1,200 teams found daily shipping cut incidents."},
        headers={HEADER: signed_in["session_id"]},
    )

    assert response.status_code == 200
    assert seen["deployment"] == "gpt-4o-mini"


def test_the_credentials_reach_the_parallel_platform_branches(
    raw_client, signed_in, studio, monkeypatch
):
    """Each platform branch runs in its own worker thread — check all three."""
    from configs.credentials import has_credentials

    bound = []
    real_ask = studio.ask

    def record(system, user, task="write", routing_text="", **kwargs):
        if task == "write":
            bound.append(has_credentials())
        return real_ask(system, user, task=task, routing_text=routing_text, **kwargs)

    monkeypatch.setattr("src.agent.ask", record)

    raw_client.post(
        "/ask",
        json={"query": "A study of 1,200 teams found daily shipping cut incidents."},
        headers={HEADER: signed_in["session_id"]},
    )

    assert len(bound) >= 3
    assert all(bound)


def test_the_context_is_cleared_once_the_request_is_done(raw_client, signed_in, studio):
    from configs.credentials import has_credentials

    raw_client.post(
        "/ask",
        json={"query": "A study of 1,200 teams found daily shipping cut incidents."},
        headers={HEADER: signed_in["session_id"]},
    )

    assert has_credentials() is False
