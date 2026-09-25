"""Loopback-only JSON API used by the Mac window and development web UI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import signal
import sys
import threading
import time
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from filinglens.config import Settings, save_env_value
from filinglens.desktop.runtime import (
    delete_api_key, delete_cloud_key, prepare_desktop_environment, read_api_key,
    read_cloud_key, save_api_key, save_cloud_key,
)
from filinglens.desktop.service import ResearchService
from filinglens.llm.base import LocalLLMError
from filinglens.sec.client import SECClientError


class ResearchRequest(BaseModel):
    ticker: str
    provider: str
    model: str
    years: int = Field(default=5, ge=3, le=10)


class QuestionRequest(ResearchRequest):
    question: str = Field(min_length=1, max_length=2000)
    filing_form: Literal["10-K", "10-Q"] = "10-K"


class SettingsUpdate(BaseModel):
    sec_user_agent: str | None = None
    ollama_cloud_key: str | None = None
    remove_ollama_cloud_key: bool = False
    openai_api_key: str | None = None
    remove_openai_api_key: bool = False
    anthropic_api_key: str | None = None
    remove_anthropic_api_key: bool = False


def create_app(service: ResearchService | None = None, token: str | None = None) -> FastAPI:
    expected_token = token if token is not None else os.getenv("FILINGLENS_API_TOKEN", "")
    if not expected_token or not expected_token.strip():
        raise ValueError("A nonempty local session token is required.")
    research = service or ResearchService()
    app = FastAPI(title="FilingLens local API", docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-FilingLens-Token"],
    )

    @app.middleware("http")
    async def local_auth(request: Request, call_next):
        from fastapi.responses import JSONResponse
        # Browser cross-origin preflight carries no session token. Let CORS
        # validate it; the subsequent data request must still authenticate.
        if request.method == "OPTIONS":
            return await call_next(request)
        if not secrets.compare_digest(request.headers.get("X-FilingLens-Token", ""), expected_token):
            return JSONResponse({"detail": "FilingLens local session authorization failed."}, status_code=401)
        return await call_next(request)

    @app.exception_handler(SECClientError)
    async def sec_error(_: Request, exc: SECClientError):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": str(exc)}, status_code=502)

    @app.exception_handler(LocalLLMError)
    async def model_error(_: Request, exc: LocalLLMError):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(ValueError)
    async def input_error(_: Request, exc: ValueError):
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "product": "FilingLens"}

    @app.get("/api/search")
    def search(q: str = ""):
        return research.search(q)

    @app.get("/api/company/{ticker}")
    def company(ticker: str, years: int = 5, refresh: bool = False):
        return research.company(ticker, years, refresh)

    @app.get("/api/company/{ticker}/provenance")
    def provenance(ticker: str, years: int = 5):
        return research.provenance(ticker, years)

    @app.get("/api/company/{ticker}/composition")
    def composition(ticker: str, form: Literal["10-K", "10-Q"] = "10-Q", years: int = 5):
        return research.composition(ticker, form, years)

    @app.get("/api/company/{ticker}/filing")
    def filing(ticker: str, years: int = 5, form: Literal["10-K", "10-Q"] = "10-K"):
        return research.filing(ticker, years, form)

    @app.get("/api/company/{ticker}/insiders")
    def insiders(ticker: str, max_filings: int = 20):
        return research.insiders(ticker, max_filings)

    @app.get("/api/providers")
    def providers():
        return research.providers()

    @app.post("/api/ask")
    def ask(payload: QuestionRequest):
        return research.ask(payload.ticker, payload.question, payload.provider, payload.model, payload.years,
                            payload.filing_form)

    @app.post("/api/brief")
    def brief(payload: ResearchRequest):
        return research.brief(payload.ticker, payload.provider, payload.model, payload.years)

    @app.get("/api/settings")
    def settings():
        current = Settings.from_env()
        return {"sec_user_agent": current.sec_user_agent,
                "ollama_cloud_key_saved": bool(read_cloud_key() or current.ollama_api_key),
                "openai_key_saved": bool(read_api_key("openai") or current.openai_api_key),
                "anthropic_key_saved": bool(read_api_key("anthropic") or current.anthropic_api_key),
                "cache_dir": str(current.cache_dir)}

    @app.post("/api/settings")
    def update_settings(payload: SettingsUpdate):
        from filinglens.config import PROJECT_ROOT
        environment = Path(os.getenv("FILINGLENS_ENV_FILE", str(PROJECT_ROOT / ".env")))
        if payload.sec_user_agent is not None:
            value = payload.sec_user_agent.strip()
            if "@" not in value or len(value) < 8:
                raise HTTPException(status_code=400, detail="Enter an SEC User-Agent with a contact email.")
            save_env_value(environment, "SEC_USER_AGENT", value)
            os.environ["SEC_USER_AGENT"] = value
        if payload.ollama_cloud_key is not None:
            save_cloud_key(payload.ollama_cloud_key)
        if payload.remove_ollama_cloud_key:
            delete_cloud_key()
            if environment.exists() and "OLLAMA_API_KEY=" in environment.read_text(encoding="utf-8"):
                save_env_value(environment, "OLLAMA_API_KEY", "")
            os.environ["OLLAMA_API_KEY"] = ""
        for provider, value, remove in (("openai", payload.openai_api_key, payload.remove_openai_api_key),
                                        ("anthropic", payload.anthropic_api_key, payload.remove_anthropic_api_key)):
            env_name = f"{provider.upper()}_API_KEY"
            if value is not None:
                save_api_key(provider, value)
            if remove:
                delete_api_key(provider)
                if environment.exists() and f"{env_name}=" in environment.read_text(encoding="utf-8"):
                    save_env_value(environment, env_name, "")
                os.environ[env_name] = ""
        return settings()

    return app


def main() -> None:
    import uvicorn
    parser = argparse.ArgumentParser(description="FilingLens local desktop API")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token-stdin", action="store_true", required=True)
    args = parser.parse_args()
    token = sys.stdin.readline().strip()
    if not token:
        parser.error("The desktop session token was not provided on stdin.")
    prepare_desktop_environment()
    if getattr(sys, "frozen", False):
        parent_pid = os.getppid()

        def stop_with_parent() -> None:
            while os.getppid() == parent_pid:
                time.sleep(1)
            os.kill(os.getpid(), signal.SIGTERM)

        threading.Thread(target=stop_with_parent, name="filinglens-parent-watch", daemon=True).start()
    uvicorn.run(create_app(token=token), host="127.0.0.1", port=args.port,
                log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
