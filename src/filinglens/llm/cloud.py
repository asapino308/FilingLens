"""Direct OpenAI and Anthropic text providers."""

from __future__ import annotations

import time

import httpx

from .base import GenerationResult, LLMProvider, LocalLLMError


class CloudProvider(LLMProvider):
    def __init__(self, service: str, api_key: str, configured_model: str = "",
                 timeout: float = 300.0, transport: httpx.BaseTransport | None = None) -> None:
        if service not in {"openai", "anthropic"}:
            raise ValueError("Unknown cloud provider.")
        self.service = service
        self.api_key = api_key
        self.configured_model = configured_model
        self.base_url = "https://api.openai.com/v1" if service == "openai" else "https://api.anthropic.com/v1"
        headers = ({"Authorization": f"Bearer {api_key}"} if service == "openai" else
                   {"x-api-key": api_key, "anthropic-version": "2023-06-01"})
        self._client = httpx.Client(headers=headers, timeout=httpx.Timeout(timeout, connect=min(timeout, 10)),
                                    transport=transport)

    def close(self) -> None:
        self._client.close()

    def list_models(self) -> list[str]:
        if not self.api_key:
            raise LocalLLMError(f"Add a {self.service.title()} API key in Settings.")
        try:
            response = self._client.get(f"{self.base_url}/models")
            response.raise_for_status()
            data = response.json()["data"]
            models = [item["id"] for item in data if isinstance(item, dict) and isinstance(item.get("id"), str)]
            if self.service == "openai":
                # The Models endpoint includes embedding, image, audio, and other non-text models.
                models = [name for name in models if name.startswith(("gpt-", "o1", "o3", "o4"))
                          and not any(part in name for part in ("audio", "realtime", "transcribe", "tts", "image", "search", "deep-research", "codex", "pro"))]
            return sorted(set(models), reverse=True)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LocalLLMError(f"{self.service.title()} model discovery failed: {exc}") from exc

    def is_available(self) -> bool:
        try:
            return bool(self.list_models())
        except LocalLLMError:
            return False

    def health_check(self) -> tuple[bool, str]:
        try:
            models = self.list_models()
            return bool(models), f"Connected — {len(models)} model(s)" if models else "No text models available."
        except LocalLLMError as exc:
            return False, str(exc)

    def generate(self, messages: list[dict[str, str]], *, model: str | None = None,
                 temperature: float = 0.2, max_tokens: int = 1200,
                 reasoning: str | None = None) -> GenerationResult:
        selected = model or self.configured_model
        if not selected:
            available = self.list_models()
            if not available:
                raise LocalLLMError(f"{self.service.title()} exposes no text models.")
            selected = available[0]
        if not self.api_key:
            raise LocalLLMError(f"Add a {self.service.title()} API key in Settings.")
        started = time.perf_counter()
        try:
            if self.service == "openai":
                payload = {"model": selected, "input": messages, "max_output_tokens": max_tokens, "store": False}
                # Some OpenAI models reject temperature/reasoning options; defaults work across families.
                response = self._client.post(f"{self.base_url}/responses", json=payload)
                response.raise_for_status()
                body = response.json()
                output = body.get("output", [])
                text = "\n".join(part.get("text", "") for item in output if item.get("type") == "message"
                                 for part in item.get("content", []) if part.get("type") == "output_text")
                usage = body.get("usage") or {}
                prompt_tokens, completion_tokens = usage.get("input_tokens"), usage.get("output_tokens")
                reasoning_tokens = (usage.get("output_tokens_details") or {}).get("reasoning_tokens")
            else:
                system = "\n\n".join(message["content"] for message in messages if message.get("role") == "system")
                conversation = [message for message in messages if message.get("role") in {"user", "assistant"}]
                payload = {"model": selected, "system": system, "messages": conversation,
                           "max_tokens": max_tokens}
                response = self._client.post(f"{self.base_url}/messages", json=payload)
                response.raise_for_status()
                body = response.json()
                text = "\n".join(part.get("text", "") for part in body.get("content", []) if part.get("type") == "text")
                usage = body.get("usage") or {}
                prompt_tokens, completion_tokens = usage.get("input_tokens"), usage.get("output_tokens")
                reasoning_tokens = None
            if not text.strip():
                raise LocalLLMError(f"{self.service.title()} returned no visible answer for '{selected}'.")
            return GenerationResult(text.strip(), selected, time.perf_counter() - started,
                                    prompt_tokens, completion_tokens, reasoning_tokens)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise LocalLLMError(f"{self.service.title()} generation failed: {exc}") from exc
