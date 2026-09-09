import urllib.error

import pytest
from langchain_openai import AzureChatOpenAI, ChatOpenAI

import configs.llms as llms
from configs.llms import _read_cache_usage


class FakeDetails:
    def __init__(self, cached_tokens):
        self.cached_tokens = cached_tokens


@pytest.fixture(autouse=True)
def _clear_caches():
    llms.get_model.cache_clear()
    llms._ollama_is_up.cache_clear()
    yield
    llms.get_model.cache_clear()
    llms._ollama_is_up.cache_clear()


@pytest.fixture
def azure_env(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-02-01")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
    monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT_SIMPLE", raising=False)


def test_read_cache_usage_handles_a_details_object_that_is_not_a_dict():
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration, LLMResult

    result = LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="hi"))]],
        llm_output={
            "model_name": "gpt-4o-mini",
            "token_usage": {
                "prompt_tokens": 2000,
                "prompt_tokens_details": FakeDetails(1500),
            },
        },
    )

    prompt_tokens, cached, _ = _read_cache_usage(result)

    assert prompt_tokens == 2000
    assert cached == 1500


def test_ollama_probe_reports_up_when_the_endpoint_answers(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeCtx())

    assert llms._ollama_is_up() is True


def test_ollama_probe_treats_an_http_error_as_reachable(monkeypatch):
    def raise_http(*args, **kwargs):
        raise urllib.error.HTTPError("url", 404, "nope", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", raise_http)

    assert llms._ollama_is_up() is True


def test_ollama_probe_reports_down_on_a_connection_error(monkeypatch):
    def raise_conn(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", raise_conn)

    assert llms._ollama_is_up() is False


def test_ollama_probe_runs_once_per_process(monkeypatch):
    calls = []

    def counting(*args, **kwargs):
        calls.append(1)
        return _FakeCtx()

    monkeypatch.setattr("urllib.request.urlopen", counting)

    llms._ollama_is_up()
    llms._ollama_is_up()
    llms._ollama_is_up()

    assert len(calls) == 1


def test_build_azure_returns_a_configured_client(azure_env):
    client = llms._build_azure("gpt-4o-mini", 0.5)

    assert isinstance(client, AzureChatOpenAI)
    assert client.temperature == 0.5
    assert llms.CACHE_LOGGER in client.callbacks


@pytest.mark.parametrize(
    "missing",
    ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_VERSION"],
)
def test_build_azure_refuses_without_its_credentials(azure_env, monkeypatch, missing):
    monkeypatch.delenv(missing, raising=False)
    if missing == "AZURE_OPENAI_API_VERSION":
        monkeypatch.setattr(llms.os, "getenv", _drop(missing))

    with pytest.raises(ValueError, match=missing):
        llms._build_azure("gpt-4o-mini", 0.7)


def test_build_azure_refuses_without_a_deployment(azure_env):
    with pytest.raises(ValueError, match="AZURE_OPENAI_DEPLOYMENT"):
        llms._build_azure("", 0.7)


def test_get_model_uses_ollama_for_the_simple_tier(monkeypatch, azure_env):
    monkeypatch.setattr(llms, "_ollama_is_up", lambda: True)

    client = llms.get_model("simple", 0.7)

    assert isinstance(client, ChatOpenAI)
    assert not isinstance(client, AzureChatOpenAI)


def test_get_model_falls_back_to_azure_when_ollama_is_down(monkeypatch, azure_env):
    monkeypatch.setattr(llms, "_ollama_is_up", lambda: False)

    assert isinstance(llms.get_model("simple", 0.7), AzureChatOpenAI)


def test_get_model_uses_azure_for_the_complex_tier(monkeypatch, azure_env):
    monkeypatch.setattr(llms, "_ollama_is_up", lambda: True)

    assert isinstance(llms.get_model("complex", 0.7), AzureChatOpenAI)


def test_get_model_treats_an_unknown_tier_as_complex(monkeypatch, azure_env):
    monkeypatch.setattr(llms, "_ollama_is_up", lambda: True)

    assert isinstance(llms.get_model("nonsense", 0.7), AzureChatOpenAI)


def test_get_model_caches_one_client_per_tier_and_temperature(monkeypatch, azure_env):
    monkeypatch.setattr(llms, "_ollama_is_up", lambda: False)

    first = llms.get_model("complex", 0.7)
    again = llms.get_model("complex", 0.7)
    warmer = llms.get_model("complex", 0.9)

    assert first is again
    assert first is not warmer


def test_load_config_returns_the_strong_tier(monkeypatch, azure_env):
    monkeypatch.setattr(llms, "_ollama_is_up", lambda: True)

    assert isinstance(llms.load_config(), AzureChatOpenAI)


def test_describe_target_names_ollama_when_it_is_up(monkeypatch):
    monkeypatch.setattr(llms, "_ollama_is_up", lambda: True)

    assert llms.describe_target("simple").startswith("ollama:")


def test_describe_target_flags_the_azure_fallback(monkeypatch, azure_env):
    monkeypatch.setattr(llms, "_ollama_is_up", lambda: False)

    described = llms.describe_target("simple")

    assert described.startswith("azure:")
    assert "ollama down" in described


def test_describe_target_names_the_deployment_for_the_complex_tier(azure_env):
    assert llms.describe_target("complex") == "azure:gpt-4o-mini"


def test_model_for_pins_a_structured_task_to_azure(monkeypatch, azure_env):
    monkeypatch.setattr(llms, "_ollama_is_up", lambda: True)

    assert isinstance(llms.model_for("router", "our launch"), AzureChatOpenAI)


def test_model_for_sends_easy_copy_to_the_cheap_tier(monkeypatch, azure_env):
    monkeypatch.setattr(llms, "_ollama_is_up", lambda: True)

    client = llms.model_for("write", "our product launch")

    assert not isinstance(client, AzureChatOpenAI)


def test_model_for_escalates_hard_source_material(monkeypatch, azure_env):
    monkeypatch.setattr(llms, "_ollama_is_up", lambda: True)

    assert isinstance(
        llms.model_for("write", "the p95 latency regression"), AzureChatOpenAI
    )


class _FakeCtx:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _drop(name):
    import os

    real = os.getenv

    def fake(key, default=None):
        if key == name:
            return None
        return real(key, default)

    return fake
