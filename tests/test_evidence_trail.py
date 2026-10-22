"""Evidence investigations preserve periods, provenance, and uncertainty."""

from copy import deepcopy

from fastapi.testclient import TestClient
import pandas as pd
import pytest

from filinglens.analytics.anomalies import detect_anomalies
from filinglens.analytics.evidence import build_evidence_trail
from filinglens.analytics.normalize import financials_wide
from filinglens.analytics.ratios import calculate_ratios
from filinglens.desktop.api import create_app
from filinglens.desktop.service import ResearchService
from filinglens.documents.chunking import chunk_sections
from filinglens.documents.retrieval import LocalRetriever
from filinglens.sec.client import SECClientError
from filinglens.sec.companies import Company


@pytest.fixture
def bundle():
    records = []
    for year, cash in ((2022, 100), (2023, 120), (2024, 50)):
        for metric, concept, value in (
            ("revenue", "Revenues", 200 + year - 2022),
            ("cost_of_revenue", "CostOfRevenue", 80),
            ("operating_cash_flow", "NetCashProvidedByUsedInOperatingActivities", cash),
            ("capital_expenditures", "PaymentsToAcquirePropertyPlantAndEquipment", 20),
            ("net_income", "NetIncomeLoss", 40),
            ("total_assets", "Assets", 400 + (year - 2022) * 20),
        ):
            records.append({"metric": metric, "fiscal_year": year, "value": value,
                            "xbrl_concept": concept, "unit": "USD", "form": "10-K",
                            "period_start": None if metric == "total_assets" else f"{year}-01-01",
                            "period_end": f"{year}-12-31", "filing_date": f"{year + 1}-02-01",
                            "accession_number": f"0000000001-{str(year + 1)[-2:]}-000001"})
    facts = pd.DataFrame(records)
    financials = financials_wide(facts)
    ratios = calculate_ratios(financials)
    return {"company": Company("TEST", "Test Company", "0000000001"),
            "facts": facts, "financials": financials, "ratios": ratios,
            "anomalies": detect_anomalies(pd.concat([financials, ratios], axis=1)),
            "submissions": {"cik": 1, "filings": {"recent": {
                "form": ["10-K"] * 4, "filingDate": ["2026-02-01", "2025-02-01", "2024-02-01", "2023-02-01"],
                "reportDate": ["2025-12-31", "2024-12-31", "2023-12-31", "2022-12-31"],
                "accessionNumber": [f"0000000001-{year}-000001" for year in (26, 25, 24, 23)],
                "primaryDocument": [f"test-{year}.htm" for year in (26, 25, 24, 23)],
            }}}}


def test_raw_movement_has_exact_comparison_values_and_source_receipts(bundle):
    trail = build_evidence_trail(bundle, "operating_cash_flow", 2024, {})
    assert trail["prior_period"] == 2023
    assert trail["movement"]["absolute_change"] == -70
    assert trail["movement"]["percentage_change"] == pytest.approx(-70 / 120)
    source = trail["movement"]["current"]["source"]
    assert source["end"] == "2024-12-31"
    assert source["filed"] == "2025-02-01"
    assert source["url"].endswith("0000000001-25-000001-index.html")
    assert len(trail["related"]) <= 3
    assert trail["passage_status"] == "not_requested"
    assert any("not establish a cause" in message for message in trail["notices"])


def test_nested_calculations_keep_each_reported_input_and_correct_period(bundle):
    trail = build_evidence_trail(bundle, "free_cash_flow_margin", 2024, {})
    current = trail["movement"]["current"]
    assert current["value"] == pytest.approx(30 / 202)
    assert current["origin"] == "calculated"
    fcf, revenue = current["inputs"]
    assert fcf["metric"] == "free_cash_flow"
    assert [item["value"] for item in fcf["inputs"]] == [50, 20]
    assert all(item["source"]["end"] == "2024-12-31" for item in fcf["inputs"] + [revenue])
    # Returns use the two balance dates, but only the current income observation.
    returns = build_evidence_trail(bundle, "return_on_assets", 2024, {})
    inputs = returns["movement"]["current"]["inputs"]
    assert [(item["metric"], item["year"]) for item in inputs] == [
        ("net_income", 2024), ("total_assets", 2023), ("total_assets", 2024)]


def test_growth_inputs_follow_calculation_row_shift(bundle):
    trail = build_evidence_trail(bundle, "operating_cash_flow_growth", 2024, {})
    assert [item["year"] for item in trail["movement"]["current"]["inputs"]] == [2023, 2024]
    assert [item["year"] for item in trail["movement"]["prior"]["inputs"]] == [2022, 2023]


def test_missing_year_is_not_mislabeled_as_a_consecutive_annual_comparison(bundle):
    bundle["financials"].loc[2023, "operating_cash_flow"] = float("nan")
    bundle["anomalies"] = detect_anomalies(pd.concat([bundle["financials"], bundle["ratios"]], axis=1))
    trail = build_evidence_trail(bundle, "operating_cash_flow", 2024, {})
    assert trail["prior_period"] == 2022
    assert any("not a consecutive-year" in message for message in trail["notices"])
    assert all(item["prior"]["year"] == 2022 for item in trail["related"])


def test_zero_prior_is_preserved_without_infinite_change(bundle):
    bundle["financials"].loc[2023, "operating_cash_flow"] = 0
    trail = build_evidence_trail(bundle, "operating_cash_flow", 2024, {})
    assert trail["movement"]["absolute_change"] == 50
    assert trail["movement"]["percentage_change"] is None


@pytest.mark.parametrize("metric,year", [("invented", 2024), ("revenue", 2022), ("revenue", 2021)])
def test_invalid_or_nonexistent_movements_are_rejected(bundle, metric, year):
    with pytest.raises(ValueError):
        build_evidence_trail(bundle, metric, year, {})


def test_review_identity_changes_when_source_context_is_revised(bundle):
    original = build_evidence_trail(bundle, "operating_cash_flow", 2024, {})
    changed = deepcopy(bundle)
    changed["facts"].loc[changed["facts"]["fiscal_year"] == 2024, "filing_date"] = "2026-02-01"
    revised = build_evidence_trail(changed, "operating_cash_flow", 2024, {})
    assert original["id"] != revised["id"]
    assert original["id"] == build_evidence_trail(bundle, "operating_cash_flow", 2024, {})["id"]


def test_passages_use_matching_historical_source_not_latest_filing(bundle, monkeypatch):
    service = ResearchService()
    monkeypatch.setattr(service, "_load", lambda *args: bundle)
    used = []

    def retrieve(loaded, filing):
        used.append(filing.accession_number)
        chunks = chunk_sections({"Management discussion": (
            "Operating cash flows decreased because collections from customers slowed. "
            "Receivables and inventory increased during the reporting period. " * 5)},
            company="Test Company", ticker="TEST", filing_form=filing.form,
            filing_date=filing.filing_date, accession_number=filing.accession_number, source_url=filing.source_url)
        return LocalRetriever(chunks), {}

    monkeypatch.setattr(service, "_retriever_for_filing", retrieve)
    trail = service.evidence("TEST", "operating_cash_flow", 2024, include_passages=True)
    assert used == ["0000000001-25-000001"]
    assert trail["passage_status"] == "available"
    assert len(trail["passages"]) == 1
    assert trail["passages"][0]["accession"] == "0000000001-25-000001"
    assert trail["passages"][0]["filed"] == "2025-02-01"


def test_missing_history_does_not_substitute_an_unrelated_current_filing(bundle, monkeypatch):
    service = ResearchService()
    bundle["submissions"]["filings"]["recent"]["reportDate"] = ["2025-12-31"]
    bundle["submissions"]["filings"]["recent"]["accessionNumber"] = ["0000000001-26-000001"]
    monkeypatch.setattr(service, "_load", lambda *args: bundle)
    monkeypatch.setattr(service, "_retriever_for_filing", lambda *args: pytest.fail("Must not read unrelated filing"))
    trail = service.evidence("TEST", "operating_cash_flow", 2024, include_passages=True)
    assert trail["passage_status"] == "unavailable"
    assert trail["passages"] == []
    assert trail["movement"]["current"]["value"] == 50


def test_document_failure_keeps_numeric_evidence_and_reports_issue(bundle, monkeypatch):
    service = ResearchService()
    monkeypatch.setattr(service, "_load", lambda *args: bundle)

    def fail(*args):
        raise SECClientError("Unavailable")

    monkeypatch.setattr(service, "_retriever_for_filing", fail)
    trail = service.evidence("TEST", "operating_cash_flow", 2024, include_passages=True)
    assert trail["passage_status"] == "partial"
    assert trail["passage_issues"]
    assert trail["movement"]["current"]["value"] == 50


def test_generic_cash_flow_hedging_policy_is_not_presented_as_operating_evidence(bundle, monkeypatch):
    service = ResearchService()
    monkeypatch.setattr(service, "_load", lambda *args: bundle)

    def retrieve(loaded, filing):
        chunks = chunk_sections({"Accounting policies": (
            "Derivative instruments and hedging gains are recorded in the same section of the cash flow statement as items being hedged, generally classified as operating activities. " * 4)},
            company="Test Company", ticker="TEST", filing_form=filing.form,
            filing_date=filing.filing_date, accession_number=filing.accession_number, source_url=filing.source_url)
        return LocalRetriever(chunks), {}

    monkeypatch.setattr(service, "_retriever_for_filing", retrieve)
    trail = service.evidence("TEST", "operating_cash_flow", 2024, include_passages=True)
    assert trail["passages"] == []
    assert trail["passage_status"] == "no_matches"


def test_evidence_endpoint_is_authenticated_validated_and_needs_no_ai(bundle, monkeypatch):
    service = ResearchService()
    monkeypatch.setattr(service, "_load", lambda *args: bundle)
    monkeypatch.setattr(service, "_provider", lambda *args: pytest.fail("Evidence must not require AI"))
    monkeypatch.setattr(service, "_retriever_for_filing", lambda *args: pytest.fail("Do not download passages until requested"))
    client = TestClient(create_app(service, token="test-evidence"))
    url = "/api/company/TEST/evidence?metric=operating_cash_flow&period=2024"
    assert client.get(url).status_code == 401
    headers = {"X-FilingLens-Token": "test-evidence"}
    response = client.get(url, headers=headers)
    assert response.status_code == 200
    assert response.json()["movement"]["current"]["value"] == 50
    assert client.get(url + "&years=99", headers=headers).status_code == 422
    assert client.get(url.replace("2024", "1900"), headers=headers).status_code == 422
    assert client.get(url.replace("operating_cash_flow", "invented"), headers=headers).status_code == 400
