import pytest

from src.agent import RULES
from src.node.accept_node import accept_node
from src.node.consistency_node import consistency_node
from src.node.manager_node import manager_node
from src.node.self_check_node import self_check_node
from src.node.writer_node import write_node
from src.routes.routing import MAX_ATTEMPTS


def platform_state(**overrides):
    base = {
        "brief": "the brief",
        "platform": "x",
        "draft": "a draft",
        "problem": "",
        "attempts": 1,
        "action_log": [],
        "trace_events": [],
    }
    base.update(overrides)
    return base


def test_manager_node_produces_the_brief(studio):
    result = manager_node({"topic": "Shipping daily reduces incidents by 40%."})

    assert result["brief"] == studio.brief
    assert result["drafts"] == {}
    assert len(result["action_log"]) == 1
    assert studio.calls == ["brief"]


def test_manager_node_emits_one_brief_trace_event(studio):
    result = manager_node({"topic": "source"})

    (record,) = result["trace_events"]
    assert record["step"] == "brief"
    assert record["actor"] == "manager"
    assert record["status"] == "done"
    assert record["duration_ms"] is not None


def test_manager_node_propagates_a_failure(studio, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("model down")

    monkeypatch.setattr("src.agent.ask", boom)

    with pytest.raises(RuntimeError):
        manager_node({"topic": "source"})


def test_write_node_produces_a_first_draft(studio):
    result = write_node(platform_state(attempts=0, draft="", problem=""))

    assert result["draft"] == studio.drafts["x"]
    assert result["attempts"] == 1
    assert result["trace_events"][0]["status"] == "drafted"
    assert studio.calls == ["write"]


def test_write_node_revises_when_a_problem_is_carried_in(studio):
    result = write_node(platform_state(attempts=1, problem="Fix the hook."))

    assert result["attempts"] == 2
    assert result["trace_events"][0]["status"] == "revised"
    assert "Fix the hook." in result["trace_events"][0]["detail"]


def test_write_node_records_the_platform_on_the_event(studio):
    result = write_node(platform_state(platform="linkedin", attempts=0, draft=""))

    assert result["trace_events"][0]["actor"] == "linkedin"


def test_self_check_fails_a_draft_over_the_character_limit(studio):
    over = "a" * (RULES["x"]["max_chars"] + 10)

    result = self_check_node(platform_state(draft=over))

    assert result["problem"] != ""
    assert "Too long" in result["problem"]
    assert studio.calls == []


def test_self_check_escalates_to_the_critic_when_length_passes(studio):
    studio.default_verdict = "OK"

    result = self_check_node(platform_state(draft="short enough"))

    assert result["problem"] == ""
    assert studio.calls == ["critique"]
    assert result["trace_events"][0]["status"] == "ok"


def test_self_check_returns_the_critics_note(studio):
    studio.set_verdicts("x", ["Replace the opening line."])

    result = self_check_node(platform_state(draft="short enough"))

    assert result["problem"] == "Replace the opening line."
    assert result["trace_events"][0]["status"] == "problem"


def test_self_check_treats_an_echoed_checklist_as_approval(studio):
    studio.set_verdicts("x", ["## Check\n1. MESSAGE — does it land?"])

    result = self_check_node(platform_state(draft="short enough"))

    assert result["problem"] == ""


def test_self_check_treats_an_empty_verdict_as_approval(studio):
    studio.set_verdicts("x", ["   "])

    result = self_check_node(platform_state(draft="short enough"))

    assert result["problem"] == ""


def test_self_check_accepts_the_draft_when_the_critic_raises(studio, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("critic down")

    monkeypatch.setattr("src.agent.ask", boom)

    result = self_check_node(platform_state(draft="short enough"))

    assert result["problem"] == ""


def test_accept_node_publishes_a_clean_draft(studio):
    result = accept_node(platform_state(draft="final text", problem="", attempts=1))

    assert result["drafts"] == {"x": "final text"}
    assert result["trace_events"][0]["status"] == "accepted"


def test_accept_node_flags_a_draft_shipped_with_a_known_issue(studio):
    result = accept_node(
        platform_state(draft="final", problem="Still weak.", attempts=MAX_ATTEMPTS)
    )

    assert result["trace_events"][0]["status"] == "accepted_as_is"
    assert "Still weak." in result["trace_events"][0]["detail"]


def test_consistency_node_passes_when_the_posts_agree(studio):
    studio.conflicts = []
    drafts = {"linkedin": "a", "x": "b", "instagram": "c"}

    result = consistency_node({"brief": "b", "drafts": drafts})

    assert "drafts" not in result
    assert result["trace_events"][0]["status"] == "ok"
    assert studio.calls == ["consistency"]


def test_consistency_node_rewrites_a_contradicting_post(studio):
    studio.conflicts = [{"platform": "x", "problem": "says 4x, LinkedIn says 40%"}]
    studio.drafts["x"] = "reconciled x post"
    drafts = {"linkedin": "a", "x": "b", "instagram": "c"}

    result = consistency_node({"brief": "b", "drafts": drafts})

    assert result["drafts"]["x"] == "reconciled x post"
    assert result["drafts"]["linkedin"] == "a"
    assert result["drafts"]["instagram"] == "c"
    assert any(e["status"] == "fixed" for e in result["trace_events"])


def test_consistency_node_ignores_a_platform_that_is_not_in_the_run(studio):
    studio.conflicts = [{"platform": "linkedin", "problem": "mismatch"}]
    drafts = {"x": "b"}

    result = consistency_node({"brief": "b", "drafts": drafts})

    assert "drafts" not in result


def test_consistency_node_keeps_the_original_when_the_rewrite_fails(studio, monkeypatch):
    studio.conflicts = [{"platform": "x", "problem": "mismatch"}]
    drafts = {"x": "original"}

    real_ask = studio.ask

    def fail_on_write(system, user, task="write", routing_text=""):
        if task == "write":
            raise RuntimeError("writer down")
        return real_ask(system, user, task=task, routing_text=routing_text)

    monkeypatch.setattr("src.agent.ask", fail_on_write)

    result = consistency_node({"brief": "b", "drafts": drafts})

    assert result["drafts"]["x"] == "original"
    assert any(e["status"] == "problem" for e in result["trace_events"])


def test_write_node_propagates_a_first_draft_failure(studio, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("writer down")

    monkeypatch.setattr("src.agent.ask", boom)

    with pytest.raises(RuntimeError):
        write_node(platform_state(attempts=0, draft="", problem=""))


def test_write_node_propagates_a_revision_failure(studio, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("writer down")

    monkeypatch.setattr("src.agent.ask", boom)

    with pytest.raises(RuntimeError):
        write_node(platform_state(attempts=1, problem="Fix the hook."))


def test_consistency_node_ships_unreconciled_when_the_check_raises(studio, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("checker down")

    monkeypatch.setattr("src.node.consistency_node.check_consistency", boom)

    result = consistency_node({"brief": "b", "drafts": {"x": "a"}})

    assert "drafts" not in result
    assert result["trace_events"][0]["status"] == "ok"
