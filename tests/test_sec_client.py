from __future__ import annotations

import json

import httpx
import pytest

from filinglens.sec.client import SECClient, SECClientError
from filinglens.sec.companies import CompanyDirectory, normalize_ticker
from filinglens.sec.submissions import latest_filing, parse_recent_filings


def test_user_agent_required(tmp_path):
    with pytest.raises(ValueError):
        SECClient("anonymous", tmp_path)


def test_headers_and_json_response(tmp_path):
    observed = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["agent"] = request.headers["user-agent"]
        return httpx.Response(200, json={"ok": True})

    client = SECClient(
        "FilingLens/1.0 test@example.com",
        tmp_path,
        min_interval=0,
        transport=httpx.MockTransport(handler),
    )
    assert client.get_json("https://data.sec.gov/example.json") == {"ok": True}
    assert observed["agent"] == "FilingLens/1.0 test@example.com"


def test_cache_prevents_second_request(tmp_path):
    count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(200, content=b"cached")

    client = SECClient(
        "FilingLens/1.0 test@example.com",
        tmp_path,
        min_interval=0,
        transport=httpx.MockTransport(handler),
    )
    url = "https://www.sec.gov/Archives/test.txt"
    assert client.get_bytes(url) == b"cached"
    assert client.get_bytes(url) == b"cached"
    assert count == 1


def test_refresh_bypasses_cache(tmp_path):
    count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(200, content=str(count).encode())

    client = SECClient(
        "FilingLens/1.0 test@example.com",
        tmp_path,
        min_interval=0,
        transport=httpx.MockTransport(handler),
    )
    url = "https://data.sec.gov/test"
    assert client.get_bytes(url) == b"1"
    assert client.get_bytes(url, refresh=True) == b"2"


def test_invalid_json_is_descriptive(tmp_path):
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"not-json"))
    client = SECClient("FilingLens/1.0 test@example.com", tmp_path, min_interval=0, transport=transport)
    with pytest.raises(SECClientError, match="invalid JSON"):
        client.get_json("https://data.sec.gov/bad.json")


def test_http_failure_retries_then_errors(tmp_path):
    count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(503)

    client = SECClient(
        "FilingLens/1.0 test@example.com",
        tmp_path,
        min_interval=0,
        max_retries=1,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(SECClientError, match="SEC request failed"):
        client.get_bytes("https://data.sec.gov/fail")
    assert count == 2


def test_throttle_waits_for_remaining_interval(tmp_path, monkeypatch):
    client = SECClient("FilingLens/1.0 test@example.com", tmp_path, min_interval=0.4)
    client._last_request = 10.0
    moments = iter([10.1, 10.5])
    sleeps = []
    monkeypatch.setattr("filinglens.sec.client.time.monotonic", lambda: next(moments))
    monkeypatch.setattr("filinglens.sec.client.time.sleep", sleeps.append)
    client._throttle()
    assert sleeps == [pytest.approx(0.3)]
    assert client._last_request == 10.5


@pytest.mark.parametrize("raw,expected", [(" aapl ", "AAPL"), ("brk.b", "BRK-B"), ("msft", "MSFT")])
def test_ticker_normalization(raw, expected):
    assert normalize_ticker(raw) == expected


@pytest.mark.parametrize("raw", ["", "AAPL!", "TOO-LONG-TICKER"])
def test_invalid_ticker(raw):
    with pytest.raises(ValueError):
        normalize_ticker(raw)


def test_company_directory_parsing():
    parsed = CompanyDirectory.parse(
        {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}
    )
    assert parsed["AAPL"].cik == "0000320193"
    assert parsed["AAPL"].name == "Apple Inc."


def test_directory_refresh_reloads_payload(tmp_path):
    responses = iter(
        [
            {"0": {"cik_str": 1, "ticker": "OLD", "title": "Old Co"}},
            {"0": {"cik_str": 2, "ticker": "NEW", "title": "New Co"}},
        ]
    )
    client = type("StubClient", (), {"company_tickers": lambda self, refresh=False: next(responses)})()
    directory = CompanyDirectory(client)
    assert "OLD" in directory.all()
    assert directory.lookup("NEW", refresh=True).cik == "0000000002"


def test_submissions_parsing_and_url():
    payload = {
        "cik": "320193",
        "filings": {
            "recent": {
                "form": ["8-K", "10-K", "10-Q"],
                "filingDate": ["2025-01-01", "2024-11-01", "2024-08-01"],
                "reportDate": ["", "2024-09-28", "2024-06-29"],
                "accessionNumber": ["x", "0000320193-24-000123", "0000320193-24-000099"],
                "primaryDocument": ["x.htm", "aapl-20240928.htm", "aapl-q3.htm"],
            }
        },
    }
    filings = parse_recent_filings(payload)
    assert [filing.form for filing in filings] == ["10-K", "10-Q"]
    assert latest_filing(payload, "10-K") == filings[0]
    assert filings[0].source_url.startswith("https://www.sec.gov/Archives/edgar/data/320193/")


def test_filing_host_is_restricted(tmp_path):
    client = SECClient("FilingLens/1.0 test@example.com", tmp_path)
    with pytest.raises(ValueError, match="official SEC"):
        client.filing_document("https://example.com/fake.htm")
