"""Ollama provider using the local native HTTP API."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .base import GenerationResult, LLMProvider, LocalLLMError


class OllamaError(LocalLLMError):
    pass


class OllamaProvider(LLMProvider):
    """Generate with models installed in a local Ollama service."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        configured_model: str = "",
        timeout: float = 300.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/").removesuffix("/v1")
        self.configured_model = configured_model
        self.timeout_seconds = timeout
        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
            headers={"Content-Type": "application/json"},
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def list_models(self) -> list[str]:
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
            raise OllamaError(f"Ollama model discovery failed: {exc}") from exc

    def is_available(self) -> bool:
        try:
            return bool(self.list_models())
        except OllamaError:
            return False

    def health_check(self) -> tuple[bool, str]:
        try:
            models = self.list_models()
        except OllamaError:
            return False, f"Ollama was not detected at {self.base_url}."
        if not models:
            return False, "Ollama is reachable, but no local chat models are installed."
        selected = self.select_model(models)
        return True, f"Connected - {selected}"

    def select_model(self, models: list[str] | None = None) -> str:
        available = models if models is not None else self.list_models()
        if self.configured_model:
            if self.configured_model not in available:
                raise OllamaError(
                    f"Configured model '{self.configured_model}' is not installed in Ollama."
                )
            return self.configured_model
        if not available:
            raise OllamaError("Ollama has no local chat models installed.")
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
                    f"The local Ollama model '{selected}' produced no visible answer within "
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
            raise OllamaError(
                f"Local Ollama generation exceeded {self.timeout_seconds:g} seconds for "
                f"'{selected}'. Try again, choose a smaller model, or increase "
                "OLLAMA_TIMEOUT_SECONDS in .env and restart FilingLens."
            ) from exc
        except OllamaError:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise OllamaError(f"Local Ollama generation failed: {exc}") from exc
