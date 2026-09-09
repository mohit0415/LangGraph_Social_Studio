import logging
import time

import pytest
from pydantic import ValidationError

from configs.logger import preview
from src.models.models import SocialInput
from src.utils.trace import STAGE_ORDER, event


def test_event_returns_every_field_the_ui_reads():
    record = event("write", "x", "drafted", detail="Wrote the draft.")

    assert set(record) == {
        "step",
        "actor",
        "status",
        "detail",
        "attempt",
        "stage",
        "ts",
        "duration_ms",
    }


@pytest.mark.parametrize("step,stage", sorted(STAGE_ORDER.items(), key=lambda kv: kv[1]))
def test_event_stamps_the_sort_stage(step, stage):
    assert event(step, "actor", "ok")["stage"] == stage


def test_event_sorts_an_unknown_step_last(caplog):
    with caplog.at_level(logging.WARNING, logger="src.utils.trace"):
        record = event("teleport", "x", "ok")

    assert record["stage"] == 99
    assert "unknown step" in caplog.text


def test_event_has_no_duration_without_a_start_time():
    assert event("write", "x", "drafted")["duration_ms"] is None


def test_event_measures_a_duration_from_a_start_time():
    started = time.perf_counter()
    time.sleep(0.01)

    duration = event("write", "x", "drafted", started=started)["duration_ms"]

    assert isinstance(duration, int)
    assert duration >= 5


def test_event_carries_the_attempt_number():
    assert event("write", "x", "revised", attempt=2)["attempt"] == 2
    assert event("write", "x", "drafted")["attempt"] is None


def test_event_timestamps_are_ordered():
    first = event("write", "x", "drafted")
    second = event("accept", "x", "accepted")

    assert second["ts"] >= first["ts"]


def test_stage_order_covers_the_whole_pipeline():
    assert set(STAGE_ORDER) == {
        "brief",
        "write",
        "self_check",
        "accept",
        "consistency",
        "refine",
    }


def test_social_input_accepts_a_query_alone():
    payload = SocialInput(query="Shipping daily reduces incidents by 40%.")

    assert payload.thread_id is None


def test_social_input_accepts_a_thread_id():
    payload = SocialInput(query="make it warmer", thread_id="abc-123")

    assert payload.thread_id == "abc-123"


def test_social_input_requires_a_query():
    with pytest.raises(ValidationError):
        SocialInput(thread_id="abc-123")


def test_social_input_warns_on_an_empty_query(caplog):
    with caplog.at_level(logging.WARNING, logger="src.models.models"):
        SocialInput(query="   ")

    assert "EMPTY query" in caplog.text


def test_social_input_warns_on_a_very_short_query(caplog):
    with caplog.at_level(logging.WARNING, logger="src.models.models"):
        SocialInput(query="too short")

    assert "very short query" in caplog.text


def test_social_input_is_quiet_for_a_healthy_query(caplog):
    with caplog.at_level(logging.WARNING, logger="src.models.models"):
        SocialInput(query="Shipping daily reduces production incidents by 40 percent.")

    assert caplog.text == ""


def test_social_input_does_not_rewrite_the_query():
    raw = "  keep   my   spacing  "

    assert SocialInput(query=raw).query == raw


def test_refine_intent_accepts_the_supported_platforms():
    from src.agent import RefineIntent

    intent = RefineIntent(
        action="refine", platforms=["linkedin", "x"], instruction="Tighten it."
    )

    assert intent.platforms == ["linkedin", "x"]


@pytest.mark.parametrize("platform", ["facebook", "tiktok", "threads", "youtube"])
def test_refine_intent_rejects_a_platform_we_do_not_write_for(platform):
    from src.agent import RefineIntent

    with pytest.raises(ValidationError):
        RefineIntent(action="refine", platforms=[platform], instruction="Tighten it.")


def test_refine_intent_rejects_an_unknown_action():
    from src.agent import RefineIntent

    with pytest.raises(ValidationError):
        RefineIntent(action="delete", platforms=[], instruction="")


def test_refine_intent_allows_an_empty_target_list():
    from src.agent import RefineIntent

    intent = RefineIntent(action="refine", platforms=[], instruction="")

    assert intent.platforms == []


def test_consistency_report_rejects_an_unknown_platform():
    from src.agent import Conflict

    with pytest.raises(ValidationError):
        Conflict(platform="facebook", problem="mismatch")


@pytest.mark.parametrize("empty", ["", None])
def test_preview_marks_empty_text(empty):
    assert preview(empty) == "<empty>"


def test_preview_collapses_whitespace():
    assert preview("a\n\n  b\tc") == "a b c"


def test_preview_returns_short_text_unchanged():
    assert preview("short") == "short"


def test_preview_truncates_and_reports_the_remainder():
    result = preview("a" * 200, limit=50)

    assert result.startswith("a" * 50)
    assert "(+150 chars)" in result
