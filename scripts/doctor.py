"""Local installation and configuration checks for FilingLens."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]


def load_simple_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def fetch_json_status(url: str) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if 200 <= response.status < 300:
                return True, f"reachable ({response.status})"
            return False, f"HTTP {response.status}"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return False, exc.__class__.__name__


def main() -> int:
    failures = 0
    warnings = 0
    print("FilingLens doctor")
    print(f"[OK] Python {sys.version.split()[0]}")
    if sys.version_info < (3, 11):
        print("[FAIL] Python 3.11 or newer is required.")
        failures += 1

    for package in ("streamlit", "pandas", "numpy", "scipy", "sklearn", "httpx", "bs4", "lxml"):
        try:
            importlib.import_module(package)
        except ImportError:
            print(f"[FAIL] Missing Python package: {package}")
            failures += 1
    if failures == 0:
        print("[OK] Required Python packages import successfully.")

    env_path = ROOT / ".env"
    env = load_simple_env(env_path)
    if not env_path.exists():
        print("[FAIL] .env is missing. Copy .env.example to .env.")
        failures += 1
    else:
        user_agent = env.get("SEC_USER_AGENT", "")
        if "@" not in user_agent or "your-email@example.com" in user_agent:
            print("[FAIL] SEC_USER_AGENT must include your real monitored contact email.")
            failures += 1
        else:
            print("[OK] SEC_USER_AGENT is configured (value not displayed).")

    provider = env.get("LOCAL_LLM_PROVIDER", "auto").lower()
    if provider not in {"auto", "lmstudio", "ollama"}:
        print("[FAIL] LOCAL_LLM_PROVIDER must be auto, lmstudio, or ollama.")
        failures += 1

    lmstudio_base = env.get("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/")
    ollama_base = env.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/").removesuffix("/v1")
    lm_ok, lm_message = fetch_json_status(f"{lmstudio_base}/models")
    ol_ok, ol_message = fetch_json_status(f"{ollama_base}/api/tags")
    print(f"[{'OK' if lm_ok else 'WARN'}] LM Studio: {lm_message}")
    print(f"[{'OK' if ol_ok else 'WARN'}] Ollama: {ol_message}")
    if not lm_ok and not ol_ok:
        print("[WARN] No local AI service detected. Financial and retrieval features still work.")
        warnings += 1

    cache_dir = ROOT / "data" / "cache"
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        probe = cache_dir / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        print("[OK] Local SEC cache directory is writable.")
    except OSError as exc:
        print(f"[FAIL] Cache directory is not writable: {exc}")
        failures += 1

    if failures:
        print(f"Doctor finished with {failures} failure(s) and {warnings} warning(s).")
        return 1
    print(f"Doctor finished successfully with {warnings} warning(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
