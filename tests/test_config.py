from __future__ import annotations

from pathlib import Path

import pytest

from filinglens.config import Settings, save_env_value


def test_save_env_value_adds_and_replaces_without_losing_other_settings(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text("SEC_USER_AGENT=FilingLens test@example.com\nOTHER=value\n")

    save_env_value(env_path, "OLLAMA_API_KEY", "first-key")
    save_env_value(env_path, "OLLAMA_API_KEY", "replacement-key")

    content = env_path.read_text(encoding="utf-8")
    assert "SEC_USER_AGENT=FilingLens test@example.com" in content
    assert "OTHER=value" in content
    assert content.count("OLLAMA_API_KEY=") == 1
    assert "OLLAMA_API_KEY=replacement-key" in content
    assert env_path.stat().st_mode & 0o777 == 0o600


def test_save_env_value_rejects_unsafe_input(tmp_path: Path):
    with pytest.raises(ValueError, match="name is invalid"):
        save_env_value(tmp_path / ".env", "bad-name", "value")
    with pytest.raises(ValueError, match="new lines"):
        save_env_value(tmp_path / ".env", "OLLAMA_API_KEY", "first\nsecond")


def test_lmstudio_timeout_is_configurable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("SEC_USER_AGENT", "FilingLens/1.0 test@example.com")
    monkeypatch.setenv("LMSTUDIO_TIMEOUT_SECONDS", "450")

    settings = Settings.from_env(tmp_path / "missing.env")

    assert settings.lmstudio_timeout_seconds == 450


def test_lmstudio_timeout_must_be_positive(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("LMSTUDIO_TIMEOUT_SECONDS", "0")

    with pytest.raises(ValueError, match="positive number"):
        Settings.from_env(tmp_path / "missing.env")


def test_ollama_and_provider_settings_are_configurable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("SEC_USER_AGENT", "FilingLens/1.0 test@example.com")
    monkeypatch.setenv("LOCAL_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/")
    monkeypatch.setenv("OLLAMA_MODEL", "gemma4:12b-mlx")
    monkeypatch.setenv("OLLAMA_TIMEOUT_SECONDS", "420")

    settings = Settings.from_env(tmp_path / "missing.env")

    assert settings.local_llm_provider == "ollama"
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.ollama_model == "gemma4:12b-mlx"
    assert settings.ollama_timeout_seconds == 420


def test_ollama_cloud_settings_are_configurable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setenv("SEC_USER_AGENT", "FilingLens/1.0 test@example.com")
    monkeypatch.setenv("AI_PROVIDER", "ollama_cloud")
    monkeypatch.setenv("OLLAMA_CLOUD_BASE_URL", "https://ollama.com/api/")
    monkeypatch.setenv("OLLAMA_CLOUD_MODEL", "gpt-oss:120b")
    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    monkeypatch.setenv("OLLAMA_CLOUD_TIMEOUT_SECONDS", "180")

    settings = Settings.from_env(tmp_path / "missing.env")

    assert settings.local_llm_provider == "ollama_cloud"
    assert settings.ollama_cloud_base_url == "https://ollama.com/api"
    assert settings.ollama_cloud_model == "gpt-oss:120b"
    assert settings.ollama_api_key == "test-key"
    assert settings.ollama_cloud_timeout_seconds == 180


def test_local_provider_must_be_supported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("AI_PROVIDER", "cloud")

    with pytest.raises(ValueError, match="ollama_cloud"):
        Settings.from_env(tmp_path / "missing.env")


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_cloud_provider_keys_and_model_are_configurable(monkeypatch: pytest.MonkeyPatch,
                                                         tmp_path: Path, provider: str):
    monkeypatch.setenv("AI_PROVIDER", provider)
    monkeypatch.setenv(f"{provider.upper()}_API_KEY", "test-key")
    monkeypatch.setenv(f"{provider.upper()}_MODEL", "model-id")
    settings = Settings.from_env(tmp_path / "missing.env")
    assert settings.local_llm_provider == provider
    assert getattr(settings, f"{provider}_api_key") == "test-key"
    assert getattr(settings, f"{provider}_model") == "model-id"
