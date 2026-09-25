from __future__ import annotations

import json

import httpx
import pytest

from filinglens.llm.ollama import (
    OllamaError,
    OllamaProvider,
    free_credit_cloud_models,
)


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
    with pytest.raises(OllamaError, match="not available"):
        provider.select_model()


def test_ollama_cloud_requires_api_key_before_network_request():
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={"models": []})

    provider = OllamaProvider(
        "https://ollama.com", cloud=True, transport=httpx.MockTransport(handler)
    )
    with pytest.raises(OllamaError, match="OLLAMA_API_KEY"):
        provider.list_models()
    assert called is False


def test_free_credit_cloud_models_are_filtered_and_stably_ordered():
    available = [
        "paid-model:large",
        "gpt-oss:20b",
        "gemma4:31b",
        "nemotron-3-super:latest",
    ]
    assert free_credit_cloud_models(available) == [
        "gemma4:31b",
        "gpt-oss:20b",
        "nemotron-3-super:latest",
    ]


def test_ollama_cloud_uses_bearer_auth_and_cloud_endpoints():
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["authorization"] = request.headers.get("Authorization")
        observed["path"] = request.url.path
        if request.url.path.endswith("/api/tags"):
            return httpx.Response(200, json={"models": [{"name": "gpt-oss:120b"}]})
        observed["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "Cloud answer"},
                "prompt_eval_count": 12,
                "eval_count": 5,
            },
        )

    provider = OllamaProvider(
        "https://ollama.com/api",
        api_key="secret-test-key",
        cloud=True,
        transport=httpx.MockTransport(handler),
    )
    assert provider.list_models() == ["gpt-oss:120b"]
    result = provider.generate(
        [{"role": "user", "content": "Question"}],
        model="gpt-oss:120b",
        reasoning="off",
    )

    assert observed["authorization"] == "Bearer secret-test-key"
    assert observed["path"] == "/api/chat"
    assert observed["payload"]["think"] is False
    assert result.text == "Cloud answer"


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


def test_ollama_cloud_payment_error_names_model_and_free_credit_options():
    transport = httpx.MockTransport(lambda request: httpx.Response(402, request=request))
    provider = OllamaProvider(
        "https://ollama.com",
        api_key="test-key",
        cloud=True,
        transport=transport,
    )

    with pytest.raises(OllamaError, match="did not authorize 'paid-model'") as exc_info:
        provider.generate(
            [{"role": "user", "content": "Question"}], model="paid-model"
        )

    assert "gemma4:31b" in str(exc_info.value)
    assert "402 Payment Required" not in str(exc_info.value)


def test_ollama_reasoning_value_is_validated():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"models": [{"name": "gemma4:12b"}]})
    )
    provider = OllamaProvider(transport=transport)
    with pytest.raises(ValueError, match="reasoning must be"):
        provider.generate([{"role": "user", "content": "Question"}], reasoning="max")
