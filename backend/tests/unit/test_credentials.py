import concurrent.futures
import contextvars

import pytest

from configs.credentials import (
    DEFAULT_API_VERSION,
    AzureCredentials,
    MissingCredentialsError,
    current_credentials,
    has_credentials,
    use_credentials,
)


def build(**overrides):
    fields = {
        "endpoint": "https://test.openai.azure.com",
        "api_key": "test-key",
        "deployment": "gpt-4o-mini",
    }
    fields.update(overrides)
    return AzureCredentials.build(**fields)


def test_build_normalises_the_endpoint_to_a_single_trailing_slash():
    assert build(endpoint="https://test.openai.azure.com///").endpoint == (
        "https://test.openai.azure.com/"
    )


def test_build_trims_surrounding_whitespace():
    creds = build(endpoint="  https://test.openai.azure.com  ", api_key="  key  ")

    assert creds.endpoint == "https://test.openai.azure.com/"
    assert creds.api_key == "key"


def test_build_defaults_the_api_version():
    assert build().api_version == DEFAULT_API_VERSION
    assert build(api_version="   ").api_version == DEFAULT_API_VERSION


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"endpoint": ""}, "endpoint is required"),
        ({"endpoint": "test.openai.azure.com"}, "full URL"),
        ({"api_key": "  "}, "API key is required"),
        ({"deployment": ""}, "deployment name is required"),
    ],
)
def test_build_names_the_field_that_is_wrong(overrides, expected):
    with pytest.raises(ValueError, match=expected):
        build(**overrides)


def test_deployment_for_falls_back_to_the_main_deployment():
    creds = build()

    assert creds.deployment_for("simple") == "gpt-4o-mini"
    assert creds.deployment_for("complex") == "gpt-4o-mini"


def test_deployment_for_uses_the_simple_deployment_when_set():
    creds = build(deployment="gpt-4o", simple_deployment="gpt-4o-mini")

    assert creds.deployment_for("simple") == "gpt-4o-mini"
    assert creds.deployment_for("complex") == "gpt-4o"


def test_the_fingerprint_is_stable_and_key_sensitive():
    assert build().fingerprint == build().fingerprint
    assert build().fingerprint != build(api_key="other").fingerprint
    assert build().fingerprint != build(deployment="gpt-4o").fingerprint


def test_the_fingerprint_does_not_leak_the_key():
    creds = build(api_key="super-secret")

    assert "super-secret" not in creds.fingerprint
    assert len(creds.fingerprint) == 16


def test_public_never_includes_the_api_key():
    public = build(api_key="super-secret").public()

    assert "api_key" not in public
    assert "super-secret" not in str(public)
    assert public["deployment"] == "gpt-4o-mini"


def test_repr_redacts_the_api_key():
    assert "super-secret" not in repr(build(api_key="super-secret"))


def test_credentials_are_immutable():
    creds = build()

    with pytest.raises(Exception):
        creds.api_key = "changed"


# --- the context var --------------------------------------------------------


def test_current_credentials_raises_when_nothing_is_bound():
    assert has_credentials() is False

    with pytest.raises(MissingCredentialsError):
        current_credentials()


def test_use_credentials_binds_and_unbinds():
    creds = build()

    with use_credentials(creds):
        assert has_credentials() is True
        assert current_credentials() is creds

    assert has_credentials() is False


def test_use_credentials_unbinds_even_when_the_block_raises():
    with pytest.raises(RuntimeError):
        with use_credentials(build()):
            raise RuntimeError("boom")

    assert has_credentials() is False


def test_nested_binding_restores_the_outer_credentials():
    outer = build(deployment="outer")
    inner = build(deployment="inner")

    with use_credentials(outer):
        with use_credentials(inner):
            assert current_credentials().deployment == "inner"
        assert current_credentials().deployment == "outer"


def test_credentials_reach_a_copied_context_in_a_worker_thread():
    """The property the parallel platform branches depend on.

    LangGraph submits each branch with ``copy_context().run(...)``; this asserts
    that a credential bound on the request thread survives that hop.
    """
    creds = build(deployment="from-the-request-thread")

    with use_credentials(creds):
        context = contextvars.copy_context()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            seen = pool.submit(context.run, lambda: current_credentials().deployment)

    assert seen.result() == "from-the-request-thread"


def test_a_plain_worker_thread_sees_no_credentials():
    """And the negative: a thread that does not copy the context gets nothing."""
    with use_credentials(build()):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            leaked = pool.submit(has_credentials)

    assert leaked.result() is False
