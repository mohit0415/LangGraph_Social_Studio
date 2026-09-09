import pytest

from configs.llms import (
    LONG_SOURCE_WORDS,
    PINNED_TASKS,
    TIERS,
    _mentions,
    assess_complexity,
    assess_with_reason,
    resolve_tier,
    supports_prompt_cache,
)


def test_mentions_matches_a_whole_word():
    assert _mentions("we ran a study on it", ["study"]) == "study"


@pytest.mark.parametrize("haystack", ["studying hard", "understudy", "studious"])
def test_mentions_does_not_match_a_substring(haystack):
    assert _mentions(haystack, ["study"]) is None


def test_mentions_returns_the_first_keyword_found():
    assert _mentions("latency and throughput", ["throughput", "latency"]) == "throughput"


@pytest.mark.parametrize(
    "text", ["p95 latency regression", "a post-mortem of the incident", "our benchmark"]
)
def test_complex_keywords_route_to_the_strong_tier(text):
    tier, reason = assess_with_reason(text)

    assert tier == "complex"
    assert "complex keyword" in reason


@pytest.mark.parametrize("text", ["our product launch", "hiring a designer", "a webinar"])
def test_simple_keywords_route_to_the_cheap_tier(text):
    tier, reason = assess_with_reason(text)

    assert tier == "simple"
    assert "simple keyword" in reason


def test_a_complex_keyword_beats_a_simple_one():
    tier, reason = assess_with_reason("announcing our latency benchmark")

    assert tier == "complex"
    assert "complex keyword" in reason


def test_a_long_source_routes_to_the_strong_tier():
    tier, reason = assess_with_reason("word " * (LONG_SOURCE_WORDS + 1))

    assert tier == "complex"
    assert "long source" in reason


def test_a_source_at_the_word_threshold_stays_simple():
    tier, _ = assess_with_reason("word " * LONG_SOURCE_WORDS)

    assert tier == "simple"


@pytest.mark.parametrize("text", ["", "   ", None])
def test_empty_source_routes_to_the_cheap_tier(text):
    tier, reason = assess_with_reason(text)

    assert tier == "simple"
    assert reason == "no text"


def test_a_short_neutral_source_defaults_to_the_cheap_tier():
    tier, reason = assess_with_reason("we changed the button colour")

    assert tier == "simple"
    assert reason.startswith("default")


def test_assess_complexity_returns_only_the_tier():
    assert assess_complexity("p95 latency") == "complex"
    assert assess_complexity("our launch") in TIERS


@pytest.mark.parametrize("task", sorted(PINNED_TASKS))
def test_pinned_tasks_ignore_the_cost_heuristic(task):
    tier, reason = resolve_tier(task, "our launch announcement")

    assert tier == "complex"
    assert "pinned" in reason


def test_an_unpinned_task_follows_the_heuristic():
    assert resolve_tier("write", "our launch announcement")[0] == "simple"
    assert resolve_tier("write", "the p95 latency regression")[0] == "complex"


def test_pinned_tasks_are_the_structured_and_strict_ones():
    assert PINNED_TASKS == {"router", "consistency", "critique"}


def test_supports_prompt_cache_is_false_for_a_non_azure_client():
    assert supports_prompt_cache(object()) is False
    assert supports_prompt_cache(None) is False


def test_supports_prompt_cache_is_true_for_azure():
    from langchain_openai import AzureChatOpenAI

    client = AzureChatOpenAI(
        api_key="test-key",
        api_version="2024-02-01",
        azure_endpoint="https://test.openai.azure.com/",
        azure_deployment="test-deployment",
    )

    assert supports_prompt_cache(client) is True
