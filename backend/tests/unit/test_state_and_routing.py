import operator
from typing import get_args, get_type_hints

import pytest
from langgraph.types import Send

from src.routes.routing import MAX_ATTEMPTS, after_self_check, fan_out
from src.schemas.state import PlatformOutput, PlatformState, State, merge_drafts


def platform_state(**overrides):
    base = {
        "brief": "brief",
        "platform": "x",
        "draft": "draft",
        "problem": "",
        "attempts": 1,
        "action_log": [],
        "trace_events": [],
    }
    base.update(overrides)
    return base


def test_merge_drafts_combines_disjoint_branches():
    merged = merge_drafts({"linkedin": "a"}, {"x": "b"})

    assert merged == {"linkedin": "a", "x": "b"}


def test_merge_drafts_lets_the_incoming_value_win():
    merged = merge_drafts({"x": "old"}, {"x": "new"})

    assert merged == {"x": "new"}


@pytest.mark.parametrize(
    "left,right,expected",
    [
        (None, {"x": "a"}, {"x": "a"}),
        ({"x": "a"}, None, {"x": "a"}),
        (None, None, {}),
        ({}, {}, {}),
    ],
)
def test_merge_drafts_tolerates_missing_sides(left, right, expected):
    assert merge_drafts(left, right) == expected


def test_merge_drafts_does_not_mutate_its_inputs():
    left = {"linkedin": "a"}
    right = {"x": "b"}

    merge_drafts(left, right)

    assert left == {"linkedin": "a"}
    assert right == {"x": "b"}


def test_merge_drafts_survives_all_three_branches_landing_together():
    merged = merge_drafts(merge_drafts({}, {"linkedin": "a"}), {"x": "b"})
    merged = merge_drafts(merged, {"instagram": "c"})

    assert sorted(merged) == ["instagram", "linkedin", "x"]


@pytest.mark.parametrize("schema", [State, PlatformState, PlatformOutput])
def test_append_only_channels_use_an_additive_reducer(schema):
    hints = get_type_hints(schema, include_extras=True)

    for channel in ("action_log", "trace_events"):
        if channel in hints:
            assert operator.add in get_args(hints[channel])


def test_drafts_uses_the_custom_merge_reducer():
    hints = get_type_hints(State, include_extras=True)

    assert merge_drafts in get_args(hints["drafts"])


def test_after_self_check_revises_while_attempts_remain():
    state = platform_state(problem="Fix the hook.", attempts=1)

    assert after_self_check(state) == "revise"


def test_after_self_check_accepts_a_clean_draft():
    state = platform_state(problem="", attempts=1)

    assert after_self_check(state) == "accept"


def test_after_self_check_accepts_once_the_budget_is_exhausted():
    state = platform_state(problem="Still wrong.", attempts=MAX_ATTEMPTS)

    assert after_self_check(state) == "accept"


def test_after_self_check_never_loops_past_the_cap():
    state = platform_state(problem="Still wrong.", attempts=MAX_ATTEMPTS + 5)

    assert after_self_check(state) == "accept"


def test_max_attempts_is_a_positive_bound():
    assert isinstance(MAX_ATTEMPTS, int)
    assert MAX_ATTEMPTS >= 1


def test_fan_out_emits_one_branch_per_platform():
    sends = fan_out({"brief": "the brief"})

    assert len(sends) == 3
    assert all(isinstance(send, Send) for send in sends)
    assert all(send.node == "platform" for send in sends)
    assert sorted(send.arg["platform"] for send in sends) == [
        "instagram",
        "linkedin",
        "x",
    ]


def test_fan_out_seeds_every_branch_with_a_clean_slate():
    for send in fan_out({"brief": "the brief"}):
        assert send.arg["brief"] == "the brief"
        assert send.arg["draft"] == ""
        assert send.arg["problem"] == ""
        assert send.arg["attempts"] == 0
        assert send.arg["action_log"] == []
        assert send.arg["trace_events"] == []
