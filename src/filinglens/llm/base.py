"""Provider-agnostic language model interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class LocalLLMError(RuntimeError):
    """Raised when a configured local language-model service cannot respond."""


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    latency_seconds: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    tokens_per_second: float | None = None


class LLMProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def list_models(self) -> list[str]: ...

    @abstractmethod
    def health_check(self) -> tuple[bool, str]: ...

    @abstractmethod
    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1200,
        reasoning: str | None = None,
    ) -> GenerationResult: ...
