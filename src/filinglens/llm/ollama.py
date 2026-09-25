"""Ollama provider using the native local or authenticated cloud HTTP API."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .base import GenerationResult, LLMProvider, LocalLLMError


FREE_CREDIT_CLOUD_MODELS = (
    "gemma4:31b",
    "gpt-oss:120b",
    "gpt-oss:20b",
    "nemotron-3-nano:30b",
    "nemotron-3-super",
    "nemotron-3-ultra",
)


def free_credit_cloud_models(available: list[str]) -> list[str]:
    """Return available free-credit models in a stable, user-friendly order."""
    matched: list[str] = []
    for preferred in FREE_CREDIT_CLOUD_MODELS:
        for model in available:
            if model == preferred or model.removesuffix(":latest") == preferred:
                if model not in matched:
                    matched.append(model)
                break
    return matched


class OllamaError(LocalLLMError):
    pass


class OllamaProvider(LLMProvider):
    """Generate with a local Ollama service or Ollama's direct cloud API."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        configured_model: str = "",
        api_key: str = "",
        cloud: bool = False,
        timeout: float = 300.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/").removesuffix("/v1").removesuffix("/api")
        self.configured_model = configured_model
        self.api_key = api_key
        self.cloud = cloud
        self.timeout_seconds = timeout
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            headers=headers,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def list_models(self) -> list[str]:
        if self.cloud and not self.api_key:
            raise OllamaError(
                "Ollama Cloud requires OLLAMA_API_KEY in .env or the environment."
            )
        try:
            response = self._client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json().get("models", [])
            discovered = [
                str(item.get("name") or item.get("model"))
                for item in data
                if isinstance(item, dict) and (item.get("name") or item.get("model"))
            ]
            return [model for model in discovered if "embed" not in model.lower()]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            service = "Ollama Cloud" if self.cloud else "Ollama"
            raise OllamaError(f"{service} model discovery failed: {exc}") from exc

    def is_available(self) -> bool:
        try:
            return bool(self.list_models())
        except OllamaError:
            return False

    def health_check(self) -> tuple[bool, str]:
        try:
            models = self.list_models()
        except OllamaError:
            service = "Ollama Cloud" if self.cloud else "Ollama"
            return False, f"{service} was not detected at {self.base_url}."
        if not models:
            location = "available" if self.cloud else "installed"
            return False, f"Ollama is reachable, but no chat models are {location}."
        selected = self.select_model(models)
        return True, f"Connected - {selected}"

    def select_model(self, models: list[str] | None = None) -> str:
        available = models if models is not None else self.list_models()
        if self.configured_model:
            if self.configured_model not in available:
                raise OllamaError(
                    f"Configured model '{self.configured_model}' is not available from Ollama."
                )
            return self.configured_model
        if not available:
            raise OllamaError("Ollama exposes no available chat models.")
        return available[0]

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        reasoning: str | None = None,
    ) -> GenerationResult:
        selected = model or self.select_model()
        think: bool | str | None = None
        if reasoning == "off":
            think = False
        elif reasoning == "on":
            think = True
        elif reasoning in {"low", "medium", "high"}:
            think = reasoning
        elif reasoning is not None:
            raise ValueError("reasoning must be off, low, medium, high, or on")

        payload: dict[str, Any] = {
            "model": selected,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if think is not None:
            payload["think"] = think

        started = time.perf_counter()
        try:
            response = self._client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
            body = response.json()
            text = body["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                raise OllamaError(
                    f"The Ollama model '{selected}' produced no visible answer within "
                    f"its {max_tokens}-token output budget."
                )
            eval_count = body.get("eval_count")
            eval_duration = body.get("eval_duration")
            tokens_per_second = None
            if isinstance(eval_count, int) and isinstance(eval_duration, int) and eval_duration > 0:
                tokens_per_second = eval_count / (eval_duration / 1_000_000_000)
            return GenerationResult(
                text=text.strip(),
                model=selected,
                latency_seconds=time.perf_counter() - started,
                prompt_tokens=body.get("prompt_eval_count"),
                completion_tokens=eval_count,
                tokens_per_second=tokens_per_second,
            )
        except httpx.TimeoutException as exc:
            service = "Ollama Cloud" if self.cloud else "Local Ollama"
            timeout_setting = (
                "OLLAMA_CLOUD_TIMEOUT_SECONDS" if self.cloud else "OLLAMA_TIMEOUT_SECONDS"
            )
            raise OllamaError(
                f"{service} generation exceeded {self.timeout_seconds:g} seconds for "
                f"'{selected}'. Try again, choose a different model, or increase "
                f"{timeout_setting} in .env and restart FilingLens."
            ) from exc
        except httpx.HTTPStatusError as exc:
            if self.cloud and exc.response.status_code == 402:
                free_models = ", ".join(FREE_CREDIT_CLOUD_MODELS)
                raise OllamaError(
                    f"Ollama Cloud did not authorize '{selected}' with the credits available "
                    f"on this account. Select one of the free-credit models ({free_models}), "
                    "check that free usage remains, or add credits in Ollama Usage settings."
                ) from exc
            if self.cloud and exc.response.status_code in {401, 403}:
                raise OllamaError(
                    "Ollama Cloud rejected the API key. Reconnect with a valid key in the "
                    "sidebar or create a new key in Ollama settings."
                ) from exc
            if self.cloud and exc.response.status_code == 429:
                raise OllamaError(
                    "Ollama Cloud temporarily rate-limited this request. Wait briefly and retry."
                ) from exc
            service = "Ollama Cloud" if self.cloud else "Local Ollama"
            raise OllamaError(
                f"{service} generation failed with HTTP {exc.response.status_code} "
                f"for '{selected}'."
            ) from exc
        except OllamaError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            service = "Ollama Cloud" if self.cloud else "Local Ollama"
            raise OllamaError(f"{service} generation failed: {exc}") from exc
