"""Responsible SEC HTTP client with caching, throttling, and retries."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any

import httpx

LOGGER = logging.getLogger(__name__)


class SECClientError(RuntimeError):
    """Raised when official SEC data cannot be obtained or validated."""


class SECClient:
    """Small SEC client designed to stay well below published request limits."""

    DATA_BASE = "https://data.sec.gov"
    WWW_BASE = "https://www.sec.gov"

    def __init__(
        self,
        user_agent: str,
        cache_dir: Path,
        min_interval: float = 0.4,
        timeout: float = 30.0,
        max_retries: int = 3,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not user_agent or "@" not in user_agent:
            raise ValueError("A descriptive SEC User-Agent with contact email is required.")
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json, text/html, */*",
        }
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval = max(min_interval, 0.0)
        self.timeout = timeout
        self.max_retries = max_retries
        self._last_request = 0.0
        self._lock = threading.Lock()
        self._client = httpx.Client(
            headers=self.headers,
            timeout=timeout,
            follow_redirects=True,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SECClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        suffix = ".json" if url.lower().split("?")[0].endswith(".json") else ".bin"
        return self.cache_dir / f"{digest}{suffix}"

    def _throttle(self) -> None:
        with self._lock:
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_request = time.monotonic()

    def get_bytes(self, url: str, *, refresh: bool = False) -> bytes:
        cache_path = self._cache_path(url)
        if cache_path.exists() and not refresh:
            return cache_path.read_bytes()

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                response = self._client.get(url)
                response.raise_for_status()
                content = response.content
                if not content:
                    raise SECClientError(f"SEC returned an empty response for {url}")
                cache_path.write_bytes(content)
                return content
            except (httpx.HTTPError, SECClientError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 8))
        raise SECClientError(f"SEC request failed for {url}: {last_error}") from last_error

    def get_json(self, url: str, *, refresh: bool = False) -> dict[str, Any]:
        try:
            payload = json.loads(self.get_bytes(url, refresh=refresh))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise SECClientError(f"SEC returned invalid JSON for {url}") from exc
        if not isinstance(payload, dict):
            raise SECClientError(f"SEC returned an unexpected JSON structure for {url}")
        return payload

    def company_tickers(self, *, refresh: bool = False) -> dict[str, Any]:
        return self.get_json(f"{self.WWW_BASE}/files/company_tickers.json", refresh=refresh)

    def submissions(self, cik: str | int, *, refresh: bool = False) -> dict[str, Any]:
        normalized = str(cik).zfill(10)
        return self.get_json(
            f"{self.DATA_BASE}/submissions/CIK{normalized}.json", refresh=refresh
        )

    def company_facts(self, cik: str | int, *, refresh: bool = False) -> dict[str, Any]:
        normalized = str(cik).zfill(10)
        return self.get_json(
            f"{self.DATA_BASE}/api/xbrl/companyfacts/CIK{normalized}.json",
            refresh=refresh,
        )

    def filing_document(self, url: str, *, refresh: bool = False) -> str:
        if not url.startswith(f"{self.WWW_BASE}/Archives/"):
            raise ValueError("Filing URLs must point to the official SEC Archives host.")
        return self.get_bytes(url, refresh=refresh).decode("utf-8", errors="replace")

