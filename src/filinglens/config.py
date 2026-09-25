"""Application configuration loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import tempfile

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def save_env_value(path: Path, key: str, value: str) -> None:
    """Add or replace one dotenv value without exposing or discarding other settings."""
    if not _ENV_KEY_PATTERN.fullmatch(key):
        raise ValueError("Environment setting name is invalid.")
    if "\n" in value or "\r" in value:
        raise ValueError("Environment setting values cannot contain new lines.")

    existing_lines = (
        path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    )
    prefix = f"{key}="
    replacement = f"{prefix}{value}"
    updated_lines: list[str] = []
    replaced = False
    for line in existing_lines:
        if line.startswith(prefix):
            if not replaced:
                updated_lines.append(replacement)
                replaced = True
            continue
        updated_lines.append(line)
    if not replaced:
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        updated_lines.append(replacement)

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temporary:
            temporary.write("\n".join(updated_lines) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)
    path.chmod(0o600)


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
    ollama_cloud_base_url: str = "https://ollama.com"
    ollama_cloud_model: str = ""
    ollama_api_key: str = ""
    ollama_cloud_timeout_seconds: float = 300.0
    openai_api_key: str = ""
    openai_model: str = ""
    anthropic_api_key: str = ""
    anthropic_model: str = ""
    cache_dir: Path = PROJECT_ROOT / "data" / "cache"
    request_interval_seconds: float = 0.4
    request_timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "Settings":
        selected_env = env_file or Path(os.getenv("FILINGLENS_ENV_FILE", str(PROJECT_ROOT / ".env")))
        load_dotenv(selected_env)
        user_agent = os.getenv("SEC_USER_AGENT", "").strip()
        provider = os.getenv(
            "AI_PROVIDER", os.getenv("LOCAL_LLM_PROVIDER", "auto")
        ).strip().lower()
        if provider not in {"auto", "lmstudio", "ollama", "ollama_cloud", "openai", "anthropic"}:
            raise ValueError(
                "AI_PROVIDER must be auto, lmstudio, ollama, ollama_cloud, openai, or anthropic."
            )
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
            ollama_cloud_base_url=os.getenv(
                "OLLAMA_CLOUD_BASE_URL", "https://ollama.com"
            ).rstrip("/"),
            ollama_cloud_model=os.getenv("OLLAMA_CLOUD_MODEL", "").strip(),
            ollama_api_key=os.getenv("OLLAMA_API_KEY", "").strip(),
            ollama_cloud_timeout_seconds=_positive_float_env(
                "OLLAMA_CLOUD_TIMEOUT_SECONDS", 300.0
            ),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_model=os.getenv("OPENAI_MODEL", "").strip(),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "").strip(),
            cache_dir=Path(os.getenv("FILINGLENS_CACHE_DIR", str(PROJECT_ROOT / "data" / "cache"))),
        )

    def validate_sec(self) -> None:
        if not self.sec_user_agent or "@" not in self.sec_user_agent:
            raise ValueError(
                "SEC_USER_AGENT must identify the application and include a contact email."
            )

    def ensure_directories(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
