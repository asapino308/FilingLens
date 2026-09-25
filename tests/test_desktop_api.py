"""Desktop API contracts and parity with the existing calculation layer."""

from fastapi.testclient import TestClient
import pandas as pd
import pytest

from filinglens.desktop.api import create_app
from filinglens.desktop import api as api_module
from filinglens.desktop.service import ResearchService
from filinglens.sec.companies import Company


def test_desktop_api_requires_native_session_token() -> None:
    client = TestClient(create_app(token="private-session"))
    assert client.get("/api/health").status_code == 401
    response = client.get("/api/health", headers={"X-FilingLens-Token": "private-session"})
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_desktop_api_refuses_missing_session_token(monkeypatch) -> None:
    monkeypatch.delenv("FILINGLENS_API_TOKEN", raising=False)
    with pytest.raises(ValueError, match="nonempty local session token"):
        create_app()
    with pytest.raises(ValueError, match="nonempty local session token"):
        create_app(token="")


def test_native_window_preflight_is_allowed_but_data_still_requires_token() -> None:
    client = TestClient(create_app(token="private-session"))
    origin = "tauri://localhost"
    preflight = client.options("/api/health", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "x-filinglens-token",
    })
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin
    denied = client.get("/api/health", headers={"Origin": origin})
    assert denied.status_code == 401
    allowed = client.get("/api/health", headers={
        "Origin": origin, "X-FilingLens-Token": "private-session",
    })
    assert allowed.status_code == 200


def test_cloud_keys_are_saved_without_being_returned(monkeypatch, tmp_path) -> None:
    saved = {}
    monkeypatch.setenv("FILINGLENS_ENV_FILE", str(tmp_path / ".env"))
    monkeypatch.setattr(api_module, "read_api_key", lambda provider: saved.get(provider, ""))
    monkeypatch.setattr(api_module, "save_api_key", lambda provider, value: saved.__setitem__(provider, value))
    monkeypatch.setattr(api_module, "delete_api_key", lambda provider: saved.pop(provider, None))
    client = TestClient(create_app(token="private-session"))
    headers = {"X-FilingLens-Token": "private-session"}
    response = client.post("/api/settings", headers=headers, json={"openai_api_key": "openai-secret",
                                                               "anthropic_api_key": "anthropic-secret"})
    assert response.status_code == 200
    assert response.json()["openai_key_saved"] and response.json()["anthropic_key_saved"]
    assert "secret" not in response.text
    assert saved == {"openai": "openai-secret", "anthropic": "anthropic-secret"}
    response = client.post("/api/settings", headers=headers, json={"remove_openai_api_key": True})
    assert response.status_code == 200
    assert not response.json()["openai_key_saved"]
    assert response.json()["anthropic_key_saved"]


def test_company_response_reuses_financials_and_preserves_missing_values(monkeypatch) -> None:
    service = ResearchService()
    years = [2023, 2024, 2025]
    financials = pd.DataFrame({
        "revenue": [100.0, 120.0, 140.0],
        "cost_of_revenue": [35.0, 42.0, 47.0],
        "gross_profit": [65.0, 78.0, 93.0],
        "operating_income": [20.0, 25.0, 30.0],
        "net_income": [15.0, 18.0, 22.0],
        "free_cash_flow": [float("nan"), 11.0, 13.0],
    }, index=years)
    ratios = pd.DataFrame({
        "revenue_growth": [float("nan"), .2, .1666667],
        "gross_margin": [.65, .65, .6642857],
    }, index=years)
    anomalies = pd.DataFrame([{
        "metric": "revenue", "period": 2025, "prior_value": 120.0,
        "current_value": 140.0, "absolute_change": 20.0,
        "percentage_change": 1 / 6, "anomaly_score": float("nan"),
        "severity": "Normal", "method": "YoY economic change",
        "explanation": "Revenue changed +16.7% versus the prior period.",
    }])
    facts = pd.DataFrame([{
        "metric": "revenue", "fiscal_year": 2025, "xbrl_concept": "Revenues",
        "filing_date": "2025-10-30", "accession_number": "0001-25-000001",
    }])
    monkeypatch.setattr(service, "_load", lambda *args, **kwargs: {
        "company": Company("TEST", "Test Company", "0000000001"),
        "submissions": {"cik": 1, "filings": {"recent": {}}},
        "financials": financials, "ratios": ratios, "anomalies": anomalies, "facts": facts,
    })
    result = service.company("TEST")
    assert result["company"]["ticker"] == "TEST"
    assert result["hero"][0]["value"] == "$140"
    assert result["statements"]["income"][0]["rows"][0]["provenance"]["concept"] == "Revenues"
    cash = result["statements"]["cash"][0]["rows"][0]
    assert cash["values"][0]["value"] is None
    assert cash["values"][0]["display"] == "—"
    assert result["anomalies"][0]["impact_direction"] == "Lightly favorable"


def test_invalid_period_count_is_rejected() -> None:
    service = ResearchService()
    try:
        service._load("AAPL", 11)
    except ValueError as error:
        assert "between 3 and 10" in str(error)
    else:
        raise AssertionError("Expected historical-period validation")
