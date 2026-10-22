"""Research features must preserve periods, versions, and calculation evidence."""

from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from filinglens.analytics.history import annual_peer, quarterly_history, revision_history
from filinglens.desktop.api import create_app
from filinglens.desktop.service import ResearchService
from filinglens.sec.companies import Company
from filinglens.sec.client import SECClientError


TAGS = {"revenue": "Revenues", "operating_income": "OperatingIncomeLoss",
        "net_income": "NetIncomeLoss", "ocf": "NetCashProvidedByUsedInOperatingActivities",
        "capex": "PaymentsToAcquirePropertyPlantAndEquipment", "assets": "Assets"}


def payload():
    return {"cik": 1, "entityName": "Research Co", "facts": {"us-gaap": {}}}


def put(data, metric, value, start, end, filed=None, accession=1, form="10-K", concept=None):
    tag = concept or TAGS[metric]
    fact = {"val": value, "end": end, "filed": filed or f"{int(end[:4]) + 1}-02-15",
            "accn": f"0000000001-{end[2:4]}-{accession:06}", "form": form, "fp": "FY"}
    if start:
        fact["start"] = start
    data["facts"]["us-gaap"].setdefault(tag, {"units": {"USD": []}})["units"]["USD"].append(fact)


def test_revision_history_keeps_reversions_and_collapses_repeated_values():
    data = payload()
    for index, value in enumerate([100, 110, 110, 100], 1):
        put(data, "revenue", value, "2023-01-01", "2023-12-31", f"2024-0{index}-20", index)
    result = revision_history(data, {})
    row = result["series"][0]
    assert [v["value"] for v in row["versions"]] == [100, 110, 100]
    assert row["versions"][1]["last_seen"] == "2024-03-20"
    assert row["versions"][1]["last_url"].endswith("0000000001-23-000003-index.html")
    assert row["revision_count"] == 2 and row["change"] == 0
    assert result["revised_series"] == 1
    assert row["versions"][0]["url"].endswith("0000000001-23-000001-index.html")


def test_revision_history_never_compares_concepts_or_different_periods():
    data = payload()
    put(data, "revenue", 100, "2023-01-01", "2023-12-31")
    put(data, "revenue", 999, "2023-01-01", "2023-12-31", "2025-02-15", 2,
        concept="SalesRevenueNet")
    put(data, "revenue", 200, "2022-12-01", "2023-12-31", "2025-02-15", 3)
    result = revision_history(data, {})
    assert len(result["series"]) == 2
    assert all(row["revision_count"] == 0 for row in result["series"])
    assert next(row for row in result["series"] if row["start"] == "2023-01-01")["latest"] == 999
    assert next(row for row in result["series"] if row["start"] == "2022-12-01")["concept"] == "Revenues"


def test_conflicting_contexts_and_nonfinite_values_are_not_revisions():
    data = payload()
    put(data, "revenue", 100, "2023-01-01", "2023-12-31")
    put(data, "revenue", 200, "2023-01-01", "2023-12-31")
    put(data, "ocf", float("inf"), "2023-01-01", "2023-12-31")
    assert revision_history(data, {})["series"] == []


def test_same_day_disagreement_is_not_an_ordered_revision():
    data = payload()
    put(data, "revenue", 100, "2023-01-01", "2023-12-31", accession=1)
    put(data, "revenue", 200, "2023-01-01", "2023-12-31", accession=2)
    assert revision_history(data, {})["series"] == []


def test_revision_impacts_recalculate_fcf_growth_and_margins():
    data = payload()
    put(data, "revenue", 100, "2022-01-01", "2022-12-31")
    put(data, "revenue", 200, "2023-01-01", "2023-12-31")
    put(data, "revenue", 250, "2023-01-01", "2023-12-31", "2025-02-15", 2)
    put(data, "operating_income", 20, "2023-01-01", "2023-12-31")
    put(data, "ocf", 50, "2023-01-01", "2023-12-31")
    put(data, "ocf", 60, "2023-01-01", "2023-12-31", "2025-02-15", 2)
    put(data, "capex", 10, "2023-01-01", "2023-12-31")
    impacts = {item["metric"]: item for item in revision_history(data, {})["impacts"]}
    assert impacts["free_cash_flow"]["first"] == 40
    assert impacts["free_cash_flow"]["latest"] == 50
    assert impacts["revenue_growth"]["first"] == 1
    assert impacts["revenue_growth"]["latest"] == 1.5
    assert impacts["operating_income_margin"]["latest"] == .08
    assert len(impacts["free_cash_flow"]["sources"]) == 3


def cash_year(data, year=2024):
    for index, (end, cumulative) in enumerate([
        (f"{year}-03-31", 10), (f"{year}-06-30", 25), (f"{year}-09-30", 45), (f"{year}-12-31", 70)
    ], 1):
        put(data, "ocf", cumulative, f"{year}-01-01", end, accession=index,
            form="10-K" if index == 4 else "10-Q")
        put(data, "capex", cumulative / 5, f"{year}-01-01", end, accession=index,
            form="10-K" if index == 4 else "10-Q")


def test_ytd_differences_and_fourth_quarter_are_derived_with_sources():
    data = payload()
    cash_year(data)
    result = quarterly_history(data, {})
    assert [p["metrics"]["operating_cash_flow"]["value"] for p in result["periods"]] == [10, 15, 20, 25]
    q2 = result["periods"][1]["metrics"]["operating_cash_flow"]
    assert q2["start"] == "2024-04-01"
    assert q2["origin"] == "ytd_difference" and len(q2["sources"]) == 2
    assert result["ttm"]["metrics"]["operating_cash_flow"]["value"] == 70
    assert result["ttm"]["metrics"]["free_cash_flow"]["value"] == 56


def test_direct_quarter_is_preferred_to_ytd_difference():
    data = payload()
    cash_year(data)
    put(data, "ocf", 16, "2024-04-01", "2024-06-30", accession=2, form="10-Q")
    row = quarterly_history(data, {})["periods"][1]["metrics"]["operating_cash_flow"]
    assert row["value"] == 16 and row["origin"] == "reported"


def test_missing_quarter_blocks_ttm_and_annual_only_does_not_create_quarters():
    data = payload()
    cash_year(data)
    data["facts"]["us-gaap"][TAGS["ocf"]]["units"]["USD"].pop(1)
    data["facts"]["us-gaap"][TAGS["capex"]]["units"]["USD"].pop(1)
    assert quarterly_history(data, {})["ttm"] is None
    annual = payload()
    put(annual, "revenue", 100, "2024-01-01", "2024-12-31")
    assert quarterly_history(annual, {})["periods"] == []


def test_cash_flow_difference_does_not_cross_concepts_or_fiscal_starts():
    data = payload()
    put(data, "capex", 10, "2024-01-01", "2024-03-31", form="10-Q")
    put(data, "capex", 30, "2023-12-15", "2024-06-30", form="10-Q", accession=2)
    put(data, "capex", 40, "2024-01-01", "2024-06-30", form="10-Q", accession=3,
        concept="PaymentsForAdditionsToPropertyPlantAndEquipment")
    result = quarterly_history(data, {})
    assert len(result["periods"]) == 1


def test_balance_sheet_is_never_summed_into_ttm():
    data = payload()
    cash_year(data)
    put(data, "assets", 1000, None, "2024-12-31")
    result = quarterly_history(data, {})
    assert result["periods"][-1]["metrics"]["total_assets"]["value"] == 1000
    assert "total_assets" not in result["ttm"]["metrics"]


def test_noncalendar_53_week_cash_year_is_contiguous():
    data = payload()
    for index, end in enumerate(["2023-04-29", "2023-07-29", "2023-10-28", "2024-02-03"], 1):
        put(data, "ocf", index * 10, "2023-01-29", end, accession=index,
            form="10-K" if index == 4 else "10-Q")
    result = quarterly_history(data, {})
    assert len(result["periods"]) == 4
    assert result["ttm"]["start"] == "2023-01-29"
    assert result["ttm"]["metrics"]["operating_cash_flow"]["value"] == 40


def test_peer_margins_require_identical_duration_and_growth_requires_prior_year():
    data = payload()
    put(data, "revenue", 100, "2021-01-01", "2021-12-31")
    put(data, "revenue", 200, "2023-01-01", "2023-12-31")
    put(data, "operating_income", 50, "2022-12-01", "2023-12-31")
    row = annual_peer(revision_history(data, {})["series"], 2023)
    assert "operating_margin" not in row["metrics"]
    assert "revenue_growth" not in row["metrics"]


def test_peer_comparison_chooses_shared_year_instead_of_each_company_latest(monkeypatch):
    first, second = payload(), payload()
    for data, years in ((first, [2022, 2023, 2024]), (second, [2021, 2022, 2023])):
        for year in years:
            put(data, "revenue", 100 + year, f"{year}-01-01", f"{year}-12-31")
    service = ResearchService()
    monkeypatch.setattr(service, "_load", lambda ticker, years: {
        "company": Company(ticker, ticker, "0000000001"),
        "company_facts": first if ticker == "A" else second,
        "submissions": {"cik": 1, "filings": {"recent": {}}},
    })
    result = service.peers(["A", "B"])
    assert result["year"] == 2023 and result["years"] == [2023, 2022]
    assert all(peer["end"] == "2023-12-31" for peer in result["companies"])


def test_peer_comparison_requires_two_successful_companies(monkeypatch):
    data = payload()
    put(data, "revenue", 100, "2023-01-01", "2023-12-31")
    service = ResearchService()
    def load(ticker, years):
        if ticker == "B":
            raise SECClientError("Unavailable")
        return {"company": Company(ticker, ticker, "0000000001"), "company_facts": data,
                "submissions": {"cik": 1, "filings": {"recent": {}}}}
    monkeypatch.setattr(service, "_load", load)
    result = service.peers(["A", "B"])
    assert result["year"] is None and result["companies"] == []
    assert result["errors"][0]["ticker"] == "B"


def test_history_and_comparison_api_contracts(monkeypatch):
    data = payload()
    cash_year(data)
    put(data, "revenue", 100, "2024-01-01", "2024-12-31")
    service = ResearchService()
    def load(ticker, years, *args):
        if ticker == "FAIL":
            raise SECClientError("Unavailable fixture")
        return {"company": Company(ticker, ticker, "0000000001"), "company_facts": deepcopy(data),
                "submissions": {"cik": 1, "filings": {"recent": {}}}}
    monkeypatch.setattr(service, "_load", load)
    client = TestClient(create_app(service, token="test"))
    headers = {"X-FilingLens-Token": "test"}
    assert client.get("/api/company/TEST/history").status_code == 401
    assert client.get("/api/company/TEST/history", headers=headers).json()["years"] == [2024]
    assert client.get("/api/company/TEST/quarters", headers=headers).json()["ttm"]["end"] == "2024-12-31"
    response = client.post("/api/peers", headers=headers, json={"tickers": ["A", "B", "FAIL"]})
    assert response.status_code == 200
    assert len(response.json()["companies"]) == 2
    assert response.json()["errors"][0]["ticker"] == "FAIL"
    assert client.post("/api/peers", headers=headers, json={"tickers": ["A", "B"], "year": 2023}).status_code == 400
    assert client.post("/api/peers", headers=headers, json={"tickers": ["A", "A"]}).status_code == 400
    assert client.post("/api/peers", headers=headers, json={"tickers": ["A"]}).status_code == 422
    assert client.post("/api/peers", headers=headers, json={"tickers": ["A", "B"], "years": 11}).status_code == 422


@pytest.mark.parametrize("method", ["history", "quarters"])
def test_history_period_limits_fail_before_network(method):
    with pytest.raises(ValueError, match="between 3 and 10"):
        getattr(ResearchService(), method)("TEST", 11)


def test_ttm_does_not_sum_different_mapped_concepts():
    data = payload()
    for index, (start, end) in enumerate([
        ('2024-01-01', '2024-03-31'), ('2024-04-01', '2024-06-30'),
        ('2024-07-01', '2024-09-30'), ('2024-10-01', '2024-12-31'),
    ]):
        put(data, 'revenue', 100, start, end, accession=index + 1, form='10-Q',
            concept='Revenues' if index < 3 else 'SalesRevenueNet')
        put(data, 'net_income', 10, start, end, accession=index + 1, form='10-Q')
    result = quarterly_history(data, {})
    assert len(result['periods']) == 4
    assert 'revenue' not in result['ttm']['metrics']
    assert result['ttm']['metrics']['net_income']['value'] == 40


def test_quarter_same_day_disagreement_is_unavailable():
    data = payload()
    for accession, value in [(1, 100), (2, 200)]:
        put(data, 'revenue', value, '2024-01-01', '2024-03-31',
            filed='2024-05-01', accession=accession, form='10-Q')
    put(data, 'net_income', 10, '2024-01-01', '2024-03-31', form='10-Q')
    result = quarterly_history(data, {})
    assert 'revenue' not in result['periods'][0]['metrics']
    assert result['periods'][0]['metrics']['net_income']['value'] == 10


def test_revision_growth_requires_comparable_annual_durations():
    data = payload()
    put(data, 'revenue', 100, '2022-01-01', '2022-12-31')
    put(data, 'revenue', 100, '2023-01-01', '2023-11-15')
    put(data, 'revenue', 120, '2023-01-01', '2023-11-15', '2025-02-15', 2)
    assert not any(item['metric'] == 'revenue_growth' for item in revision_history(data, {})['impacts'])


def test_quarter_balance_sheet_same_day_conflict_is_unavailable():
    data = payload()
    cash_year(data)
    put(data, 'assets', 1000, None, '2024-12-31', accession=1)
    put(data, 'assets', 2000, None, '2024-12-31', accession=2)
    assert 'total_assets' not in quarterly_history(data, {})['periods'][-1]['metrics']
