import pytest

from src.agent import RULES, ask, ask_structured, write_post


class FakeResponse:
    def __init__(self, content):
        self.content = content


class FakeStructured:
    def __init__(self, result, error=None):
        self.result = result
        self.error = error
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return self.result


class FakeLLM:
    def __init__(self, content="  the answer  ", error=None, structured=None):
        self.content = content
        self.error = error
        self.structured = structured
        self.messages = None
        self.schema = None

    def invoke(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return FakeResponse(self.content)

    def with_structured_output(self, schema):
        self.schema = schema
        return self.structured


@pytest.fixture
def llm(monkeypatch):
    client = FakeLLM()
    monkeypatch.setattr("src.agent.model_for", lambda *a, **k: client)
    return client


def test_ask_returns_the_stripped_content(llm):
    assert ask("system", "user") == "the answer"


def test_ask_sends_the_system_and_user_turns(llm):
    ask("SYSTEM", "USER")

    assert llm.messages[-1] == ("human", "USER")
    assert ("system", "SYSTEM") in llm.messages


def test_ask_routes_on_the_task_and_the_routing_text(monkeypatch):
    seen = {}

    def spy(task, text="", temperature=0.7):
        seen["task"] = task
        seen["text"] = text
        return FakeLLM()

    monkeypatch.setattr("src.agent.model_for", spy)
    ask("s", "u", task="critique", routing_text="the brief")

    assert seen == {"task": "critique", "text": "the brief"}


def test_ask_propagates_a_model_failure(monkeypatch):
    monkeypatch.setattr(
        "src.agent.model_for", lambda *a, **k: FakeLLM(error=RuntimeError("down"))
    )

    with pytest.raises(RuntimeError):
        ask("s", "u")


def test_ask_structured_returns_the_validated_object(monkeypatch):
    from src.agent import RefineIntent

    expected = RefineIntent(action="refine", platforms=["x"], instruction="Tighten it.")
    client = FakeLLM(structured=FakeStructured(expected))
    monkeypatch.setattr("src.agent.model_for", lambda *a, **k: client)

    result = ask_structured(RefineIntent, "s", "u", "router", fallback=None)

    assert result is expected
    assert client.schema is RefineIntent


def test_ask_structured_returns_the_fallback_on_failure(monkeypatch):
    from src.agent import RefineIntent

    fallback = RefineIntent(action="refine", platforms=[], instruction="")
    client = FakeLLM(structured=FakeStructured(None, error=ValueError("no tools")))
    monkeypatch.setattr("src.agent.model_for", lambda *a, **k: client)

    result = ask_structured(RefineIntent, "s", "u", "router", fallback=fallback)

    assert result is fallback


def test_ask_structured_never_raises_when_a_fallback_exists(monkeypatch):
    from src.agent import ConsistencyReport

    fallback = ConsistencyReport(conflicts=[])
    client = FakeLLM(structured=FakeStructured(None, error=RuntimeError("boom")))
    monkeypatch.setattr("src.agent.model_for", lambda *a, **k: client)

    assert ask_structured(ConsistencyReport, "s", "u", "consistency", fallback) is fallback


@pytest.mark.parametrize("platform", ["linkedin", "x", "instagram"])
def test_write_post_builds_a_platform_specific_prompt(llm, platform):
    write_post(platform, "the brief")

    system = next(text for role, text in llm.messages if role == "system")

    assert platform in system
    assert str(RULES[platform]["max_chars"]) in system


def test_write_post_sends_the_brief_as_the_task(llm):
    write_post("x", "THE BRIEF")

    assert "THE BRIEF" in llm.messages[-1][1]


def test_write_post_includes_the_previous_draft_when_revising(llm):
    write_post("x", "THE BRIEF", fix="Cut the filler.", old_draft="OLD DRAFT")

    user = llm.messages[-1][1]

    assert "OLD DRAFT" in user
    assert "Cut the filler." in user


def test_write_post_rejects_an_unknown_platform(llm):
    with pytest.raises(KeyError):
        write_post("facebook", "the brief")


def test_self_critique_shows_the_critic_its_previous_note(llm):
    from src.agent import self_critique

    self_critique("x", "brief", "draft", attempt=2, previous_problem="Fix the hook.")

    user = llm.messages[-1][1]

    assert "Fix the hook." in user
    assert "attempt 2 of 3" in user


def test_self_critique_warns_the_critic_on_the_final_pass(llm):
    from src.agent import self_critique

    self_critique(
        "x", "brief", "draft", attempt=3, previous_problem="Fix it.", max_attempts=3
    )

    assert "FINAL pass" in llm.messages[-1][1]


def test_check_consistency_maps_conflicts_by_platform(monkeypatch):
    from src.agent import Conflict, ConsistencyReport, check_consistency

    report = ConsistencyReport(conflicts=[Conflict(platform="x", problem="mismatch")])
    client = FakeLLM(structured=FakeStructured(report))
    monkeypatch.setattr("src.agent.model_for", lambda *a, **k: client)

    result = check_consistency("brief", {"x": "a", "linkedin": "b"})

    assert result == {"x": "mismatch"}


def test_check_consistency_drops_a_platform_absent_from_the_run(monkeypatch):
    from src.agent import Conflict, ConsistencyReport, check_consistency

    report = ConsistencyReport(
        conflicts=[Conflict(platform="instagram", problem="mismatch")]
    )
    client = FakeLLM(structured=FakeStructured(report))
    monkeypatch.setattr("src.agent.model_for", lambda *a, **k: client)

    assert check_consistency("brief", {"x": "a"}) == {}


def test_route_message_passes_prior_edits_as_history(monkeypatch):
    from src.agent import RefineIntent, route_message

    intent = RefineIntent(action="refine", platforms=["x"], instruction="Tighten it.")
    client = FakeLLM(structured=FakeStructured(intent))
    monkeypatch.setattr("src.agent.model_for", lambda *a, **k: client)

    route_message("do the same for X", ["[linkedin] refined on request: warmer"])

    assert "refined on request: warmer" in client.structured.messages[-1][1]


def test_route_message_says_so_when_there_is_no_history(monkeypatch):
    from src.agent import RefineIntent, route_message

    intent = RefineIntent(action="new", platforms=[], instruction="")
    client = FakeLLM(structured=FakeStructured(intent))
    monkeypatch.setattr("src.agent.model_for", lambda *a, **k: client)

    route_message("a fresh article", [])

    assert "no edits yet" in client.structured.messages[-1][1]
