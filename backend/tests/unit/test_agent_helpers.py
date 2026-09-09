import pytest

from src.agent import (
    MAX_CRITIQUE_CHARS,
    RULES,
    _is_malformed,
    _is_ok,
    _messages,
    check_length,
)
from src.utils.prompts import SHARED_PREFIX


class FakeAzure:
    pass


class FakeLocal:
    pass


@pytest.fixture(autouse=True)
def _cache_support(monkeypatch):
    monkeypatch.setattr(
        "src.agent.supports_prompt_cache",
        lambda llm: isinstance(llm, FakeAzure),
    )


@pytest.mark.parametrize(
    "platform,limit",
    [("linkedin", 3000), ("x", 280), ("instagram", 2200)],
)
def test_check_length_accepts_a_draft_within_the_limit(platform, limit):
    assert check_length(platform, "a" * limit) == ""
    assert check_length(platform, "") == ""


@pytest.mark.parametrize("platform", ["linkedin", "x", "instagram"])
def test_check_length_reports_the_overflow(platform):
    limit = RULES[platform]["max_chars"]
    problem = check_length(platform, "a" * (limit + 25))

    assert problem != ""
    assert str(limit) in problem
    assert str(limit + 25) in problem
    assert "25" in problem


def test_check_length_rejects_an_unknown_platform():
    with pytest.raises(KeyError):
        check_length("threads", "hello")


@pytest.mark.parametrize(
    "verdict",
    ["OK", "ok", "OK.", "**OK**", '"OK"', "  OK  ", "`OK`", "OK - looks good"],
)
def test_is_ok_accepts_decorated_approvals(verdict):
    assert _is_ok(verdict) is True


def test_is_ok_accepts_a_verdict_on_the_final_line():
    assert _is_ok("The hook works.\nFacts match the brief.\nOK") is True


@pytest.mark.parametrize(
    "verdict",
    ["Replace the opening line.", "Not OK", "", "Cut the third paragraph."],
)
def test_is_ok_rejects_a_real_critique(verdict):
    assert _is_ok(verdict) is False


def test_is_malformed_flags_an_overlong_verdict():
    assert _is_malformed("x" * (MAX_CRITIQUE_CHARS + 1)) is True


@pytest.mark.parametrize(
    "echo",
    ["## Check", "## How to answer", "1. MESSAGE — does it land?", "3. TONE"],
)
def test_is_malformed_flags_an_echoed_checklist(echo):
    assert _is_malformed(f"Here is my review.\n{echo}\nsomething") is True


def test_is_malformed_accepts_a_one_sentence_note():
    assert _is_malformed("Replace the opening line, it states the obvious.") is False


def test_messages_puts_the_cacheable_prefix_first_on_azure():
    built = _messages(FakeAzure(), "ROLE PROMPT", "USER CONTENT")

    assert len(built) == 3
    assert built[0] == ("system", SHARED_PREFIX)
    assert built[1] == ("system", "ROLE PROMPT")
    assert built[2] == ("human", "USER CONTENT")


def test_messages_omits_the_prefix_for_a_provider_without_a_cache():
    built = _messages(FakeLocal(), "ROLE PROMPT", "USER CONTENT")

    assert built == [("system", "ROLE PROMPT"), ("human", "USER CONTENT")]


def test_messages_keeps_variable_content_last():
    built = _messages(FakeAzure(), "ROLE", "the brief and the draft")

    assert built[-1][0] == "human"
    assert all(role == "system" for role, _ in built[:-1])
