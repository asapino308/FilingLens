from __future__ import annotations

import json

import httpx
import pytest

from filinglens.llm.base import LocalLLMError
from filinglens.llm.cloud import CloudProvider


@pytest.mark.parametrize("service,models_path,generation_path", [
    ("openai", "/v1/models", "/v1/responses"),
    ("anthropic", "/v1/models", "/v1/messages"),
])
def test_cloud_provider_discovers_and_generates(service, models_path, generation_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if service == "openai":
            assert request.headers["authorization"] == "Bearer test-key"
        else:
            assert request.headers["x-api-key"] == "test-key"
            assert request.headers["anthropic-version"] == "2023-06-01"
        if request.url.path == models_path:
            ids = ["gpt-4.1-mini", "text-embedding-3-small"] if service == "openai" else ["claude-sonnet-4-5"]
            return httpx.Response(200, json={"data": [{"id": value} for value in ids]})
        assert request.url.path == generation_path
        payload = json.loads(request.content)
        assert payload["model"] == ("gpt-4.1-mini" if service == "openai" else "claude-sonnet-4-5")
        if service == "openai":
            assert payload["store"] is False
            assert payload["input"][0]["role"] == "system"
            return httpx.Response(200, json={"output": [{"type": "message", "content": [{"type": "output_text", "text": "Grounded answer"}]}], "usage": {"input_tokens": 10, "output_tokens": 3}})
        assert payload["system"] == "Use filing evidence"
        assert payload["messages"] == [{"role": "user", "content": "Question"}]
        return httpx.Response(200, json={"content": [{"type": "text", "text": "Grounded answer"}], "usage": {"input_tokens": 10, "output_tokens": 3}})

    provider = CloudProvider(service, "test-key", transport=httpx.MockTransport(handler))
    try:
        assert provider.list_models() == (["gpt-4.1-mini"] if service == "openai" else ["claude-sonnet-4-5"])
        result = provider.generate([{"role": "system", "content": "Use filing evidence"},
                                    {"role": "user", "content": "Question"}])
        assert result.text == "Grounded answer"
        assert result.prompt_tokens == 10
    finally:
        provider.close()


def test_cloud_provider_requires_key_and_rejects_empty_answer():
    provider = CloudProvider("openai", "")
    with pytest.raises(LocalLLMError, match="API key"):
        provider.list_models()
    provider.close()
    provider = CloudProvider("anthropic", "test-key", "claude-sonnet-4-5",
                             transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"content": []})))
    with pytest.raises(LocalLLMError, match="no visible answer"):
        provider.generate([{"role": "user", "content": "Question"}])
    provider.close()
