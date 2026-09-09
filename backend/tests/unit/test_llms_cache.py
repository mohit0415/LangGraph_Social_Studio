import logging

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from configs.llms import (
    CACHE_MIN_PROMPT_TOKENS,
    CacheUsageHandler,
    _read_cache_usage,
)


def azure_result(prompt_tokens, cached_tokens, model="gpt-4o-mini-2024-07-18"):
    return LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="hi"))]],
        llm_output={
            "model_name": model,
            "token_usage": {
                "prompt_tokens": prompt_tokens,
                "prompt_tokens_details": {"cached_tokens": cached_tokens},
            },
        },
    )


def metadata_result(input_tokens, cache_read):
    message = AIMessage(
        content="hi",
        usage_metadata={
            "input_tokens": input_tokens,
            "output_tokens": 5,
            "total_tokens": input_tokens + 5,
            "input_token_details": {"cache_read": cache_read},
        },
    )
    return LLMResult(generations=[[ChatGeneration(message=message)]], llm_output={})


def bare_result():
    return LLMResult(
        generations=[[ChatGeneration(message=AIMessage(content="hi"))]],
        llm_output={"model_name": "llama3.1:8b", "token_usage": {"prompt_tokens": 300}},
    )


def test_read_cache_usage_reads_the_azure_shape():
    prompt_tokens, cached, written = _read_cache_usage(azure_result(2048, 1536))

    assert prompt_tokens == 2048
    assert cached == 1536
    assert written == 0


def test_read_cache_usage_reads_a_zero_hit_as_zero_not_none():
    _, cached, _ = _read_cache_usage(azure_result(2048, 0))

    assert cached == 0


def test_read_cache_usage_falls_back_to_usage_metadata():
    prompt_tokens, cached, _ = _read_cache_usage(metadata_result(1800, 1024))

    assert prompt_tokens == 1800
    assert cached == 1024


def test_read_cache_usage_returns_none_when_the_provider_is_silent():
    prompt_tokens, cached, _ = _read_cache_usage(bare_result())

    assert prompt_tokens == 300
    assert cached is None


def test_handler_logs_a_hit_with_the_share(caplog):
    handler = CacheUsageHandler()

    with caplog.at_level(logging.INFO, logger="configs.llms"):
        handler.on_llm_end(azure_result(2000, 1500))

    text = caplog.text
    assert "prompt cache HIT" in text
    assert "1500/2000" in text
    assert "75%" in text


def test_handler_logs_a_miss_below_the_minimum(caplog):
    handler = CacheUsageHandler()

    with caplog.at_level(logging.INFO, logger="configs.llms"):
        handler.on_llm_end(azure_result(300, 0))

    assert "prompt cache MISS" in caplog.text
    assert str(CACHE_MIN_PROMPT_TOKENS) in caplog.text


def test_handler_explains_the_minimum_only_once(caplog):
    handler = CacheUsageHandler()

    with caplog.at_level(logging.INFO, logger="configs.llms"):
        handler.on_llm_end(azure_result(300, 0))
        handler.on_llm_end(azure_result(310, 0))
        handler.on_llm_end(azure_result(320, 0))

    assert caplog.text.count("cannot engage") == 1
    assert caplog.text.count("prompt cache MISS") == 3


def test_handler_logs_a_cold_miss_above_the_minimum(caplog):
    handler = CacheUsageHandler()

    with caplog.at_level(logging.INFO, logger="configs.llms"):
        handler.on_llm_end(azure_result(CACHE_MIN_PROMPT_TOKENS + 500, 0))

    assert "prompt cache MISS" in caplog.text
    assert "first call of the run" in caplog.text


def test_handler_is_quiet_for_a_provider_without_a_cache(caplog):
    handler = CacheUsageHandler()

    with caplog.at_level(logging.INFO, logger="configs.llms"):
        handler.on_llm_end(bare_result())

    assert "prompt cache HIT" not in caplog.text
    assert "prompt cache MISS" not in caplog.text


def test_handler_never_raises_on_a_malformed_response():
    handler = CacheUsageHandler()

    assert handler.on_llm_end(object()) is None
