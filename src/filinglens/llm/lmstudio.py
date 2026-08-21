"""OpenAI-compatible LM Studio provider using local HTTP only."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .base import GenerationResult, LLMProvider, LocalLLMError


class LMStudioError(LocalLLMError):
    pass


class LMStudioProvider(LLMProvider):
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:1234/v1",
        configured_model: str = "",
        api_key: str = "",
        timeout: float = 300.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.configured_model = configured_model
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
        try:
            response = self._client.get(f"{self.base_url}/models")
            response.raise_for_status()
            data = response.json().get("data", [])
            discovered = [
                str(item["id"]) for item in data if isinstance(item, dict) and item.get("id")
            ]
            # LM Studio exposes embedding and generation models on the same endpoint.
            # Common embedding IDs are excluded from the chat-model selector.
            return [model for model in discovered if "embed" not in model.lower()]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LMStudioError(f"LM Studio model discovery failed: {exc}") from exc

    def is_available(self) -> bool:
        try:
            return bool(self.list_models())
        except LMStudioError:
            return False

    def health_check(self) -> tuple[bool, str]:
        try:
            models = self.list_models()
        except LMStudioError:
            return False, f"LM Studio was not detected at {self.base_url}."
        if not models:
            return False, "LM Studio is reachable, but it exposes no loaded models."
        selected = self.select_model(models)
        return True, f"Connected — {selected}"

    def select_model(self, models: list[str] | None = None) -> str:
        available = models if models is not None else self.list_models()
        if self.configured_model:
            if self.configured_model not in available:
                raise LMStudioError(
                    f"Configured model '{self.configured_model}' is not exposed by LM Studio."
                )
            return self.configured_model
        if not available:
            raise LMStudioError("LM Studio exposes no loaded models.")
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
        if reasoning is not None:
            return self._generate_native(
                messages,
                model=selected,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning=reasoning,
            )
        payload: dict[str, Any] = {
            "model": selected,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        started = time.perf_counter()
        try:
            response = self._client.post(f"{self.base_url}/chat/completions", json=payload)
            response.raise_for_status()
            body = response.json()
            text = body["choices"][0]["message"]["content"]
            if not isinstance(text, str) or not text.strip():
                finish_reason = body.get("choices", [{}])[0].get("finish_reason")
                raise LMStudioError(self._empty_response_message(selected, max_tokens, finish_reason))
            usage = body.get("usage", {})
            return GenerationResult(
                text=text.strip(),
                model=selected,
                latency_seconds=time.perf_counter() - started,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
            )
        except httpx.TimeoutException as exc:
            raise LMStudioError(self._timeout_message(selected)) from exc
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise LMStudioError(f"Local model generation failed: {exc}") from exc

    def _generate_native(
        self,
        messages: list[dict[str, str]],
        *,
        model: str,
        temperature: float,
        max_tokens: int,
        reasoning: str,
    ) -> GenerationResult:
        """Use LM Studio's native endpoint when explicit reasoning control is needed."""
        if reasoning not in {"off", "low", "medium", "high", "on"}:
            raise ValueError("reasoning must be off, low, medium, high, or on")
        system_prompt = "\n\n".join(
            message["content"] for message in messages if message.get("role") == "system"
        )
        input_text = "\n\n".join(
            message["content"] for message in messages if message.get("role") != "system"
        )
        payload = {
            "model": model,
            "input": input_text,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "max_output_tokens": max_tokens,
            "reasoning": reasoning,
            "store": False,
        }
        api_root = self.base_url.removesuffix("/v1")
        started = time.perf_counter()
        try:
            response = self._client.post(f"{api_root}/api/v1/chat", json=payload)
            response.raise_for_status()
            body = response.json()
            text = "\n".join(
                str(item.get("content", ""))
                for item in body.get("output", [])
                if isinstance(item, dict) and item.get("type") == "message"
            ).strip()
            if not text:
                raise LMStudioError(self._empty_response_message(model, max_tokens))
            stats = body.get("stats", {})
            return GenerationResult(
                text=text,
                model=model,
                latency_seconds=time.perf_counter() - started,
                prompt_tokens=stats.get("input_tokens"),
                completion_tokens=stats.get("total_output_tokens"),
                reasoning_tokens=stats.get("reasoning_output_tokens"),
                tokens_per_second=stats.get("tokens_per_second"),
            )
        except httpx.TimeoutException as exc:
            raise LMStudioError(self._timeout_message(model)) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LMStudioError(f"Local model generation failed: {exc}") from exc

    def _timeout_message(self, model: str) -> str:
        seconds = f"{self.timeout_seconds:g}"
        return (
            f"Local model generation exceeded {seconds} seconds for '{model}'. "
            "A newly selected ticker uses different filing evidence, so LM Studio cannot reuse "
            "the previous prompt cache and the first response may be slower. Wait for any active "
            "LM Studio job to finish, try a smaller/faster model, or increase "
            "LMSTUDIO_TIMEOUT_SECONDS in .env and restart FilingLens."
        )

    @staticmethod
    def _empty_response_message(
        model: str, max_tokens: int, finish_reason: str | None = None
    ) -> str:
        suffix = f" (finish reason: {finish_reason})" if finish_reason else ""
        return (
            f"The local model '{model}' produced no visible answer within its {max_tokens}-token "
            f"output budget{suffix}. This is a model-generation issue, not an out-of-scope "
            "decision. Try again or select a different local model."
        )
