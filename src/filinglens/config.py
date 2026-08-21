"""Application configuration loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _positive_float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive number of seconds.") from exc
    if value <= 0:
        raise ValueError(f"{name} must be a positive number of seconds.")
    return value


@dataclass(frozen=True)
class Settings:
    """Runtime settings with safe local defaults."""

    sec_user_agent: str
    local_llm_provider: str = "auto"
    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    lmstudio_model: str = ""
    lmstudio_api_key: str = ""
    lmstudio_timeout_seconds: float = 300.0
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    ollama_timeout_seconds: float = 300.0
    cache_dir: Path = PROJECT_ROOT / "data" / "cache"
    request_interval_seconds: float = 0.4
    request_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        load_dotenv(env_file or PROJECT_ROOT / ".env")
        user_agent = os.getenv("SEC_USER_AGENT", "").strip()
        provider = os.getenv("LOCAL_LLM_PROVIDER", "auto").strip().lower()
        if provider not in {"auto", "lmstudio", "ollama"}:
            raise ValueError("LOCAL_LLM_PROVIDER must be auto, lmstudio, or ollama.")
        return cls(
            sec_user_agent=user_agent,
            local_llm_provider=provider,
            lmstudio_base_url=os.getenv(
                "LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1"
            ).rstrip("/"),
            lmstudio_model=os.getenv("LMSTUDIO_MODEL", "").strip(),
            lmstudio_api_key=os.getenv("LMSTUDIO_API_KEY", "").strip(),
            lmstudio_timeout_seconds=_positive_float_env(
                "LMSTUDIO_TIMEOUT_SECONDS", 300.0
            ),
            ollama_base_url=os.getenv(
                "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
            ).rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "").strip(),
            ollama_timeout_seconds=_positive_float_env(
                "OLLAMA_TIMEOUT_SECONDS", 300.0
            ),
        )

    def validate_sec(self) -> None:
        if not self.sec_user_agent or "@" not in self.sec_user_agent:
            raise ValueError(
                "SEC_USER_AGENT must identify the application and include a contact email."
            )

    def ensure_directories(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
