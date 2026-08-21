"""High-level official filing retrieval helpers."""

from __future__ import annotations

from .client import SECClient
from .submissions import FilingMetadata, parse_recent_filings


def available_filings(
    client: SECClient, cik: str, forms: tuple[str, ...] = ("10-K", "10-Q")
) -> list[FilingMetadata]:
    return parse_recent_filings(client.submissions(cik), forms)


def fetch_filing(client: SECClient, filing: FilingMetadata, refresh: bool = False) -> str:
    return client.filing_document(filing.source_url, refresh=refresh)

