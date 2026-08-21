"""Ticker normalization and SEC company directory lookup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .client import SECClient, SECClientError


@dataclass(frozen=True)
class Company:
    ticker: str
    name: str
    cik: str


def normalize_ticker(ticker: str) -> str:
    cleaned = ticker.strip().upper().replace(".", "-")
    if not cleaned or len(cleaned) > 10 or not all(c.isalnum() or c == "-" for c in cleaned):
        raise ValueError("Enter a valid U.S. ticker symbol.")
    return cleaned


class CompanyDirectory:
    def __init__(self, sec_client: SECClient) -> None:
        self.sec_client = sec_client
        self._by_ticker: dict[str, Company] | None = None

    @staticmethod
    def parse(payload: dict[str, Any]) -> dict[str, Company]:
        companies: dict[str, Company] = {}
        for record in payload.values():
            if not isinstance(record, dict):
                continue
            ticker = str(record.get("ticker", "")).strip().upper()
            cik = record.get("cik_str")
            title = str(record.get("title", "")).strip()
            if ticker and cik is not None:
                companies[ticker] = Company(ticker=ticker, name=title, cik=str(cik).zfill(10))
        return companies

    def all(self, *, refresh: bool = False) -> dict[str, Company]:
        if self._by_ticker is None or refresh:
            self._by_ticker = self.parse(self.sec_client.company_tickers(refresh=refresh))
        return self._by_ticker

    def lookup(self, ticker: str, *, refresh: bool = False) -> Company:
        normalized = normalize_ticker(ticker)
        company = self.all(refresh=refresh).get(normalized)
        if company is None:
            raise SECClientError(f"Ticker {normalized} was not found in the SEC company directory.")
        return company
