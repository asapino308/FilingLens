from __future__ import annotations

from pathlib import Path

import pytest

from filinglens.config import Settings


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


def test_local_provider_must_be_supported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("LOCAL_LLM_PROVIDER", "cloud")

    with pytest.raises(ValueError, match="auto, lmstudio, or ollama"):
        Settings.from_env(tmp_path / "missing.env")
