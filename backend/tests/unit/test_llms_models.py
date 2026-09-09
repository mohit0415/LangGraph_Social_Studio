import pytest
from langchain_openai import AzureChatOpenAI

import configs.llms as llms
from configs.credentials import (
    AzureCredentials,
    MissingCredentialsError,
    use_credentials,
)
from configs.llms import _read_cache_usage


class FakeDetails:
    def __init__(self, cached_tokens):
        self.cached_tokens = cached_tokens


@pytest.fixture(autouse=True)
def _clear_cache():
    llms.clear_model_cache()
    yield
    llms.clear_model_cache()


@pytest.fixture
def creds():
    return AzureCredentials.build(
        endpoint="https://test.openai.azure.com",
        api_key="test-key",
        deployment="gpt-4o-mini",
        api_version="2024-02-01",
    )


@pytest.fixture
def tiered_creds():
    return AzureCredentials.build(
        endpoint="https://test.openai.azure.com",
        api_key="test-key",
        deployment="gpt-4o",
        api_version="2024-02-01",
        simple_deployment="gpt-4o-mini",
    )


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


def test_build_azure_client_returns_a_configured_client(creds):
    client = llms.build_azure_client(creds, "gpt-4o-mini", 0.5)

    assert isinstance(client, AzureChatOpenAI)
    assert client.temperature == 0.5
    assert llms.CACHE_LOGGER in client.callbacks


def test_build_azure_client_refuses_without_a_deployment(creds):
    with pytest.raises(ValueError, match="deployment"):
        llms.build_azure_client(creds, "", 0.7)


def test_build_azure_client_accepts_overrides(creds):
    client = llms.build_azure_client(creds, "gpt-4o-mini", 0.0, max_retries=0, callbacks=[])

    assert client.max_retries == 0
    assert client.callbacks == []


# --- the environment is not a credential source any more --------------------


def test_get_model_refuses_when_no_credentials_are_bound():
    with pytest.raises(MissingCredentialsError):
        llms.get_model("complex", 0.7)


def test_get_model_ignores_azure_environment_variables(monkeypatch):
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://env.openai.azure.com/")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "env-deployment")

    with pytest.raises(MissingCredentialsError):
        llms.get_model("complex", 0.7)


def test_the_module_has_no_way_to_read_the_environment():
    """Structural, not behavioural: it never imports os or dotenv at all."""
    assert not hasattr(llms, "os")
    assert not hasattr(llms, "load_dotenv")


def test_the_ollama_tier_is_gone():
    for name in ("_ollama_is_up", "OLLAMA_BASE_URL", "OLLAMA_MODEL"):
        assert not hasattr(llms, name)

    assert llms.TIERS == {"simple", "complex"}


# --- tier routing -----------------------------------------------------------


def test_get_model_uses_the_bound_credentials(creds):
    with use_credentials(creds):
        client = llms.get_model("complex", 0.7)

    assert isinstance(client, AzureChatOpenAI)
    assert client.deployment_name == "gpt-4o-mini"


def test_both_tiers_share_one_deployment_by_default(creds):
    with use_credentials(creds):
        simple = llms.get_model("simple", 0.7)
        complex_ = llms.get_model("complex", 0.7)

    assert simple is complex_


def test_the_simple_tier_uses_its_own_deployment_when_given_one(tiered_creds):
    with use_credentials(tiered_creds):
        simple = llms.get_model("simple", 0.7)
        complex_ = llms.get_model("complex", 0.7)

    assert simple.deployment_name == "gpt-4o-mini"
    assert complex_.deployment_name == "gpt-4o"
    assert simple is not complex_


def test_get_model_treats_an_unknown_tier_as_complex(tiered_creds):
    with use_credentials(tiered_creds):
        assert llms.get_model("nonsense", 0.7).deployment_name == "gpt-4o"


def test_load_config_returns_the_strong_tier(tiered_creds):
    with use_credentials(tiered_creds):
        assert llms.load_config().deployment_name == "gpt-4o"


# --- caching ----------------------------------------------------------------


def test_get_model_caches_one_client_per_deployment_and_temperature(creds):
    with use_credentials(creds):
        first = llms.get_model("complex", 0.7)
        again = llms.get_model("complex", 0.7)
        warmer = llms.get_model("complex", 0.9)

    assert first is again
    assert first is not warmer


def test_two_users_never_share_a_cached_client(creds):
    other = AzureCredentials.build(
        endpoint="https://other.openai.azure.com",
        api_key="other-key",
        deployment="gpt-4o-mini",
        api_version="2024-02-01",
    )

    with use_credentials(creds):
        mine = llms.get_model("complex", 0.7)
    with use_credentials(other):
        theirs = llms.get_model("complex", 0.7)

    assert mine is not theirs
    assert theirs.azure_endpoint == "https://other.openai.azure.com/"


def test_forget_models_drops_only_that_users_clients(creds):
    other = AzureCredentials.build(
        endpoint="https://other.openai.azure.com",
        api_key="other-key",
        deployment="gpt-4o-mini",
    )

    with use_credentials(creds):
        mine = llms.get_model("complex", 0.7)
    with use_credentials(other):
        theirs = llms.get_model("complex", 0.7)

    dropped = llms.forget_models(creds.fingerprint)

    assert dropped == 1
    with use_credentials(other):
        assert llms.get_model("complex", 0.7) is theirs
    with use_credentials(creds):
        assert llms.get_model("complex", 0.7) is not mine


def test_forget_models_is_quiet_about_an_unknown_fingerprint():
    assert llms.forget_models("never-seen") == 0


# --- describe_target --------------------------------------------------------


def test_describe_target_names_the_deployment(creds):
    with use_credentials(creds):
        assert llms.describe_target("complex") == "azure:gpt-4o-mini"


def test_describe_target_flags_a_shared_simple_tier(creds):
    with use_credentials(creds):
        described = llms.describe_target("simple")

    assert described.startswith("azure:gpt-4o-mini")
    assert "shared with complex" in described


def test_describe_target_names_a_dedicated_simple_deployment(tiered_creds):
    with use_credentials(tiered_creds):
        assert llms.describe_target("simple") == "azure:gpt-4o-mini"


def test_describe_target_does_not_raise_without_credentials():
    assert "no credentials" in llms.describe_target("complex")


# --- model_for --------------------------------------------------------------


def test_model_for_pins_a_structured_task_to_the_strong_deployment(tiered_creds):
    with use_credentials(tiered_creds):
        assert llms.model_for("router", "our launch").deployment_name == "gpt-4o"


def test_model_for_sends_easy_copy_to_the_cheap_deployment(tiered_creds):
    with use_credentials(tiered_creds):
        client = llms.model_for("write", "our product launch")

    assert client.deployment_name == "gpt-4o-mini"


def test_model_for_escalates_hard_source_material(tiered_creds):
    with use_credentials(tiered_creds):
        client = llms.model_for("write", "the p95 latency regression")

    assert client.deployment_name == "gpt-4o"
