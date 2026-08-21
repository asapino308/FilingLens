from __future__ import annotations

import json

import httpx
import pytest

from filinglens.llm.ollama import OllamaError, OllamaProvider


def test_ollama_model_discovery_and_selection():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"models": [{"name": "gemma4:12b-mlx"}, {"model": "qwen3:8b"}]},
        )
    )
    provider = OllamaProvider(transport=transport)
    assert provider.list_models() == ["gemma4:12b-mlx", "qwen3:8b"]
    assert provider.select_model() == "gemma4:12b-mlx"
    assert provider.health_check() == (True, "Connected - gemma4:12b-mlx")


def test_ollama_embedding_models_are_not_offered_for_chat():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={"models": [{"name": "gemma4:12b"}, {"name": "nomic-embed-text"}]},
        )
    )
    assert OllamaProvider(transport=transport).list_models() == ["gemma4:12b"]


def test_ollama_configured_model_must_be_installed():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"models": [{"name": "gemma4:e2b"}]})
    )
    provider = OllamaProvider(configured_model="missing", transport=transport)
    with pytest.raises(OllamaError, match="not installed"):
        provider.select_model()


def test_ollama_generation_disables_thinking_and_records_usage():
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/tags"):
            return httpx.Response(200, json={"models": [{"name": "gemma4:12b-mlx"}]})
        observed.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "Grounded answer [Source 1]"},
                "prompt_eval_count": 20,
                "eval_count": 10,
                "eval_duration": 2_000_000_000,
            },
        )

    provider = OllamaProvider(transport=httpx.MockTransport(handler))
    result = provider.generate(
        [{"role": "user", "content": "Question"}],
        reasoning="off",
        max_tokens=900,
    )
    assert observed["model"] == "gemma4:12b-mlx"
    assert observed["think"] is False
    assert observed["stream"] is False
    assert observed["options"]["num_predict"] == 900
    assert observed["options"]["temperature"] == 0.2
    assert result.text.endswith("[Source 1]")
    assert result.prompt_tokens == 20
    assert result.completion_tokens == 10
    assert result.tokens_per_second == pytest.approx(5.0)


def test_ollama_unavailable_server_is_graceful():
    transport = httpx.MockTransport(lambda request: httpx.Response(503))
    provider = OllamaProvider(transport=transport)
    assert provider.is_available() is False
    available, message = provider.health_check()
    assert available is False
    assert "not detected" in message


def test_ollama_timeout_is_actionable():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/api/tags"):
            return httpx.Response(200, json={"models": [{"name": "gemma4:12b"}]})
        raise httpx.ReadTimeout("timed out", request=request)

    provider = OllamaProvider(timeout=45, transport=httpx.MockTransport(handler))
    with pytest.raises(OllamaError, match="exceeded 45 seconds") as exc_info:
        provider.generate([{"role": "user", "content": "Question"}])
    assert "OLLAMA_TIMEOUT_SECONDS" in str(exc_info.value)


def test_ollama_reasoning_value_is_validated():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"models": [{"name": "gemma4:12b"}]})
    )
    provider = OllamaProvider(transport=transport)
    with pytest.raises(ValueError, match="reasoning must be"):
        provider.generate([{"role": "user", "content": "Question"}], reasoning="max")
