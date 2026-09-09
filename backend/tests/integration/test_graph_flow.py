import pytest
from langgraph.checkpoint.memory import MemorySaver

from src.agent import RULES
from src.graphs.graph import build_graph
from src.routes.routing import MAX_ATTEMPTS


@pytest.fixture
def graph():
    return build_graph(MemorySaver())


def initial_state(topic="Shipping daily reduces incidents by 40%."):
    return {
        "topic": topic,
        "brief": "",
        "drafts": {},
        "action_log": [],
        "trace_events": [],
    }


def run(graph, thread_id="t-test", topic="Shipping daily reduces incidents by 40%."):
    config = {"configurable": {"thread_id": thread_id}}
    return graph.invoke(initial_state(topic), config=config), config


def events_for(result, platform):
    return [e for e in result["trace_events"] if e["actor"] == platform]


def test_a_run_produces_one_post_per_platform(studio, graph):
    result, _ = run(graph)

    assert set(result["drafts"]) == set(RULES)
    assert all(text for text in result["drafts"].values())


def test_a_run_writes_the_brief_before_fanning_out(studio, graph):
    result, _ = run(graph)

    assert result["brief"] == studio.brief
    assert studio.calls[0] == "brief"


def test_the_three_platforms_run_in_parallel_from_one_brief(studio, graph):
    result, _ = run(graph)

    assert studio.calls.count("brief") == 1
    assert studio.calls.count("write") == 3


def test_a_clean_run_writes_each_post_once(studio, graph):
    studio.default_verdict = "OK"

    result, _ = run(graph)

    for platform in RULES:
        writes = [e for e in events_for(result, platform) if e["step"] == "write"]
        assert len(writes) == 1


def test_a_rejected_draft_is_revised_and_re_checked(studio, graph):
    studio.set_verdicts("x", ["Replace the opening line.", "OK"])

    result, _ = run(graph)

    x_writes = [e for e in events_for(result, "x") if e["step"] == "write"]
    x_checks = [e for e in events_for(result, "x") if e["step"] == "self_check"]

    assert len(x_writes) == 2
    assert x_writes[1]["status"] == "revised"
    assert len(x_checks) == 2


def test_only_the_rejected_platform_is_rewritten(studio, graph):
    studio.set_verdicts("x", ["Replace the opening line.", "OK"])

    result, _ = run(graph)

    assert len([e for e in events_for(result, "x") if e["step"] == "write"]) == 2
    assert len([e for e in events_for(result, "linkedin") if e["step"] == "write"]) == 1
    assert len([e for e in events_for(result, "instagram") if e["step"] == "write"]) == 1


def test_the_loop_stops_at_max_attempts(studio, graph):
    studio.default_verdict = "Still weak."

    result, _ = run(graph)

    for platform in RULES:
        writes = [e for e in events_for(result, platform) if e["step"] == "write"]
        assert len(writes) == MAX_ATTEMPTS


def test_an_unresolved_draft_is_accepted_as_is(studio, graph):
    studio.default_verdict = "Still weak."

    result, _ = run(graph)

    accepts = [e for e in result["trace_events"] if e["step"] == "accept"]

    assert len(accepts) == 3
    assert all(e["status"] == "accepted_as_is" for e in accepts)


def test_an_overlong_draft_is_caught_without_calling_the_critic(studio, graph):
    studio.drafts["x"] = "a" * (RULES["x"]["max_chars"] + 50)

    result, _ = run(graph)

    x_checks = [e for e in events_for(result, "x") if e["step"] == "self_check"]

    assert x_checks[0]["status"] == "problem"
    assert "Too long" in x_checks[0]["detail"]


def test_the_consistency_pass_runs_once_at_the_end(studio, graph):
    result, _ = run(graph)

    consistency = [e for e in result["trace_events"] if e["step"] == "consistency"]

    assert len(consistency) == 1
    assert studio.calls[-1] == "consistency"


def test_the_consistency_pass_reconciles_a_contradiction(studio, graph):
    studio.conflicts = [{"platform": "x", "problem": "says 4x, LinkedIn says 40%"}]

    result, _ = run(graph)

    assert any(
        e["step"] == "consistency" and e["status"] == "fixed"
        for e in result["trace_events"]
    )


def test_the_action_log_accumulates_across_every_branch(studio, graph):
    result, _ = run(graph)

    log = result["action_log"]

    assert any("[manager]" in line for line in log)
    assert any("[consistency]" in line for line in log)
    for platform in RULES:
        assert any(f"[{platform}]" in line for line in log)


def test_state_is_checkpointed_and_reloadable(studio, graph):
    result, config = run(graph, thread_id="reload-me")

    saved = graph.get_state(config).values

    assert saved["drafts"] == result["drafts"]
    assert saved["brief"] == result["brief"]


def test_two_threads_do_not_share_state(studio, graph):
    run(graph, thread_id="thread-a", topic="First source about a launch.")
    run(graph, thread_id="thread-b", topic="Second source about latency.")

    a = graph.get_state({"configurable": {"thread_id": "thread-a"}}).values
    b = graph.get_state({"configurable": {"thread_id": "thread-b"}}).values

    assert a["topic"] != b["topic"]
    assert set(a["drafts"]) == set(b["drafts"]) == set(RULES)


def test_update_state_replaces_only_the_named_draft(studio, graph):
    result, config = run(graph, thread_id="refine-me")
    original_linkedin = result["drafts"]["linkedin"]

    graph.update_state(config, {"drafts": {"x": "hand edited"}})
    saved = graph.get_state(config).values

    assert saved["drafts"]["x"] == "hand edited"
    assert saved["drafts"]["linkedin"] == original_linkedin
