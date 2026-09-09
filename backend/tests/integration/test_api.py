import pytest

from src.agent import RULES

SOURCE = "A study of 1,200 engineering teams found daily shipping cut incidents 40%."


def create_thread(client, studio, source=SOURCE):
    response = client.post("/ask", json={"query": source})
    assert response.status_code == 200
    return response.json()


def test_post_ask_creates_a_thread_with_three_posts(client, studio):
    body = create_thread(client, studio)

    assert body["action"] == "new"
    assert body["thread_id"]
    assert set(body["posts"]) == set(RULES)
    assert body["brief"] == studio.brief


def test_a_new_thread_returns_its_trace_and_transcript(client, studio):
    body = create_thread(client, studio)

    assert body["trace"]
    assert body["events"]
    assert body["messages"] == [{"role": "user", "text": SOURCE}]


def test_every_new_thread_gets_a_distinct_id(client, studio):
    first = create_thread(client, studio)
    second = create_thread(client, studio)

    assert first["thread_id"] != second["thread_id"]


def test_get_threads_lists_a_created_thread(client, studio):
    body = create_thread(client, studio)

    listing = client.get("/threads")
    assert listing.status_code == 200

    ids = [row["thread_id"] for row in listing.json()["threads"]]
    assert body["thread_id"] in ids


def test_the_thread_list_carries_a_title_and_message_count(client, studio):
    body = create_thread(client, studio)

    rows = client.get("/threads").json()["threads"]
    row = next(r for r in rows if r["thread_id"] == body["thread_id"])

    assert row["title"]
    assert row["message_count"] == 1
    assert row["created_at"] <= row["updated_at"]


def test_the_thread_list_is_newest_first(client, studio):
    create_thread(client, studio)
    newest = create_thread(client, studio)

    rows = client.get("/threads").json()["threads"]

    assert rows[0]["thread_id"] == newest["thread_id"]


def test_get_a_thread_returns_the_saved_posts(client, studio):
    created = create_thread(client, studio)

    loaded = client.get(f"/threads/{created['thread_id']}")

    assert loaded.status_code == 200
    assert loaded.json()["action"] == "load"
    assert loaded.json()["posts"] == created["posts"]


def test_get_an_unknown_thread_is_a_404(client, studio):
    response = client.get("/threads/does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Unknown thread_id."


def test_a_follow_up_refines_only_the_named_platform(client, studio):
    created = create_thread(client, studio)
    studio.router_intent = {
        "action": "refine",
        "platforms": ["x"],
        "instruction": "Tighten the opening.",
    }
    studio.drafts["x"] = "a tightened x post"

    response = client.post(
        "/ask", json={"query": "tighten the X post", "thread_id": created["thread_id"]}
    )
    body = response.json()

    assert body["action"] == "refine"
    assert body["refined"] == ["x"]
    assert body["posts"]["x"] == "a tightened x post"
    assert body["posts"]["linkedin"] == created["posts"]["linkedin"]


def test_a_refinement_is_persisted_for_the_next_load(client, studio):
    created = create_thread(client, studio)
    studio.router_intent = {
        "action": "refine",
        "platforms": ["instagram"],
        "instruction": "Make it warmer.",
    }
    studio.drafts["instagram"] = "a warmer instagram post"

    client.post(
        "/ask", json={"query": "warmer please", "thread_id": created["thread_id"]}
    )
    loaded = client.get(f"/threads/{created['thread_id']}").json()

    assert loaded["posts"]["instagram"] == "a warmer instagram post"


def test_a_refinement_appends_to_the_transcript(client, studio):
    created = create_thread(client, studio)
    studio.router_intent = {
        "action": "refine",
        "platforms": ["x"],
        "instruction": "Tighten it.",
    }

    body = client.post(
        "/ask", json={"query": "tighten it", "thread_id": created["thread_id"]}
    ).json()

    roles = [m["role"] for m in body["messages"]]
    assert roles == ["user", "user", "system"]
    assert "Tighten it." in body["messages"][-1]["text"]


def test_a_vague_follow_up_asks_instead_of_guessing(client, studio):
    created = create_thread(client, studio)
    studio.router_intent = {"action": "refine", "platforms": [], "instruction": ""}
    before = created["posts"]

    body = client.post(
        "/ask", json={"query": "make it better", "thread_id": created["thread_id"]}
    ).json()

    assert body["action"] == "clarify"
    assert body["message"]
    assert "all" in body["options"]
    assert body["posts"] == before


def test_a_named_platform_with_no_instruction_asks_what_to_change(client, studio):
    created = create_thread(client, studio)
    studio.router_intent = {"action": "refine", "platforms": ["x"], "instruction": ""}

    body = client.post(
        "/ask", json={"query": "improve the tweet", "thread_id": created["thread_id"]}
    ).json()

    assert body["action"] == "clarify"
    assert "x" in body["message"]


def test_fresh_source_on_an_existing_thread_starts_a_new_thread(client, studio):
    created = create_thread(client, studio)
    studio.router_intent = {"action": "new", "platforms": [], "instruction": ""}

    body = client.post(
        "/ask",
        json={"query": "A totally different article.", "thread_id": created["thread_id"]},
    ).json()

    assert body["action"] == "new"
    assert body["thread_id"] != created["thread_id"]


def test_a_follow_up_can_refine_every_platform_at_once(client, studio):
    created = create_thread(client, studio)
    studio.router_intent = {
        "action": "refine",
        "platforms": ["linkedin", "x", "instagram"],
        "instruction": "Cut the filler.",
    }
    for platform in RULES:
        studio.drafts[platform] = f"rewritten {platform}"

    body = client.post(
        "/ask", json={"query": "tighten them all up", "thread_id": created["thread_id"]}
    ).json()

    assert sorted(body["refined"]) == sorted(RULES)
    for platform in RULES:
        assert body["posts"][platform] == f"rewritten {platform}"


def test_delete_removes_the_thread_from_the_list_and_the_checkpoints(client, studio):
    created = create_thread(client, studio)
    thread_id = created["thread_id"]

    deleted = client.delete(f"/threads/{thread_id}")

    assert deleted.status_code == 200
    assert deleted.json() == {"thread_id": thread_id, "deleted": True}

    ids = [row["thread_id"] for row in client.get("/threads").json()["threads"]]
    assert thread_id not in ids
    assert client.get(f"/threads/{thread_id}").status_code == 404


def test_deleting_an_unknown_thread_is_not_an_error(client, studio):
    response = client.delete("/threads/never-existed")

    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_get_platforms_exposes_the_character_limits(client, studio):
    response = client.get("/platforms")

    assert response.status_code == 200
    body = response.json()
    for platform, rule in RULES.items():
        assert str(rule["max_chars"]) in str(body)
        assert platform in str(body)


def test_a_query_is_required(client, studio):
    response = client.post("/ask", json={"thread_id": "abc"})

    assert response.status_code == 422


def test_a_generation_failure_becomes_a_500(client, studio, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("model down")

    monkeypatch.setattr("src.agent.ask", boom)

    response = client.post("/ask", json={"query": SOURCE})

    assert response.status_code == 500
    assert response.json()["detail"] == "Content generation failed."


def test_a_refinement_failure_becomes_a_500(client, studio, monkeypatch):
    created = create_thread(client, studio)
    studio.router_intent = {
        "action": "refine",
        "platforms": ["x"],
        "instruction": "Tighten it.",
    }

    real_ask = studio.ask

    def fail_on_write(system, user, task="write", routing_text="", **kwargs):
        if task == "write":
            raise RuntimeError("writer down")
        return real_ask(system, user, task=task, routing_text=routing_text)

    monkeypatch.setattr("src.agent.ask", fail_on_write)

    response = client.post(
        "/ask", json={"query": "tighten it", "thread_id": created["thread_id"]}
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Refinement failed."


def test_a_clarify_names_the_instruction_when_the_target_is_missing(client, studio):
    created = create_thread(client, studio)
    studio.router_intent = {
        "action": "refine",
        "platforms": [],
        "instruction": "Cut the third paragraph.",
    }

    body = client.post(
        "/ask", json={"query": "cut the third paragraph", "thread_id": created["thread_id"]}
    ).json()

    assert body["action"] == "clarify"
    assert "Cut the third paragraph." in body["message"]


def test_delete_still_reports_success_when_checkpoint_removal_fails(
    client, studio, api, monkeypatch
):
    created = create_thread(client, studio)

    def boom(thread_id):
        raise RuntimeError("checkpointer down")

    monkeypatch.setattr(api.checkpointer, "delete_thread", boom)

    response = client.delete(f"/threads/{created['thread_id']}")

    assert response.status_code == 200
    ids = [row["thread_id"] for row in client.get("/threads").json()["threads"]]
    assert created["thread_id"] not in ids


def test_health_reports_the_database_in_use(client, studio):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"].endswith(".db")
