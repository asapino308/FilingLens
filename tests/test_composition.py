"""Filing-bound composition and revenue-reconciliation behavior."""

from fastapi.testclient import TestClient

from filinglens.desktop.api import create_app
from filinglens.sec.composition import (
    compose_income, revenue_disaggregations, select_filing_income_facts,
)


def _fact(value: float, *, start: str = "2026-01-01", end: str = "2026-03-31",
          accession: str = "q-1", form: str = "10-Q") -> dict:
    return {"val": value, "start": start, "end": end, "accn": accession,
            "form": form, "filed": "2026-04-20"}


def test_selects_exact_filing_and_quarter_without_ytd_mix():
    payload = {"facts": {"us-gaap": {
        "RevenueFromContractWithCustomerExcludingAssessedTax": {"units": {"USD": [
            _fact(100), _fact(290, start="2025-10-01"), _fact(80, accession="q-older"),
        ]}},
        "OperatingExpenses": {"units": {"USD": [_fact(30), _fact(75, start="2025-10-01")]}},
        "IncomeTaxExpenseBenefit": {"units": {"USD": [_fact(5, start="2026-01-03")]}}
    }}}
    result = select_filing_income_facts(payload, "q-1", "2026-03-31", "10-Q")
    assert result["revenue"]["value"] == 100
    assert result["operating_expenses"]["value"] == 30
    assert result["revenue"]["period_start"] == "2026-01-01"
    assert "income_tax" not in result


def test_expense_detail_uses_sga_aggregate_once_and_marks_calculated_items():
    start, end = "2026-01-01", "2026-03-31"
    def row(name, value):
        return {"id": name, "label": name, "value": value, "concept": name,
                "period_start": start, "period_end": end, "origin": "reported"}
    facts = {name: row(name, value) for name, value in {
        "revenue": 100, "cost_of_revenue": 40, "operating_expenses": 25,
        "operating_income": 35, "research_development": 10,
        "selling_general_admin": 12, "selling_marketing": 8, "general_admin": 4,
        "income_before_tax": 37, "income_tax": 7, "net_income": 30,
    }.items()}
    result = compose_income(facts)
    assert result["metrics"]["gross_profit"]["value"] == 60
    assert result["metrics"]["gross_profit"]["origin"] == "calculated"
    assert result["metrics"]["net_nonoperating"]["value"] == 2
    assert result["reconciliations"] == {"gross_profit": True, "operating_income": True, "net_income": True}
    assert [item["id"] for item in result["expense_details"]] == [
        "research_development", "selling_general_admin", "other_unmapped_operating",
    ]
    assert result["expense_details"][-1]["value"] == 3


def test_reported_lines_that_do_not_reconcile_are_not_described_as_a_simple_subtraction():
    start, end = "2026-01-01", "2026-03-31"
    def row(name, value):
        return {"id": name, "label": name, "value": value, "concept": name,
                "period_start": start, "period_end": end, "origin": "reported"}
    result = compose_income({
        "revenue": row("revenue", 100), "cost_of_revenue": row("cost_of_revenue", 40),
        "gross_profit": row("gross_profit", 50), "operating_expenses": row("operating_expenses", 20),
        "operating_income": row("operating_income", 35),
    })
    assert result["reconciliations"]["gross_profit"] is False
    assert result["reconciliations"]["operating_income"] is False
    assert result["reconciliations"]["net_income"] is None


def test_revenue_splits_reconcile_and_do_not_mix_periods_or_parent_categories():
    html = """<html><body>
    <xbrli:context id="product"><xbrli:period><xbrli:startDate>2026-01-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period><xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">us-gaap:ProductMember</xbrldi:explicitMember></xbrli:context>
    <xbrli:context id="a"><xbrli:period><xbrli:startDate>2026-01-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period><xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">test:AlphaMember</xbrldi:explicitMember></xbrli:context>
    <xbrli:context id="b"><xbrli:period><xbrli:startDate>2026-01-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period><xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">test:BetaMember</xbrldi:explicitMember></xbrli:context>
    <xbrli:context id="service"><xbrli:period><xbrli:startDate>2026-01-01</xbrli:startDate><xbrli:endDate>2026-03-31</xbrli:endDate></xbrli:period><xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">us-gaap:ServiceMember</xbrldi:explicitMember></xbrli:context>
    <xbrli:context id="old"><xbrli:period><xbrli:startDate>2025-10-01</xbrli:startDate><xbrli:endDate>2025-12-31</xbrli:endDate></xbrli:period><xbrldi:explicitMember dimension="srt:ProductOrServiceAxis">test:OldMember</xbrldi:explicitMember></xbrli:context>
    <table><tr><td>Products</td><td><ix:nonFraction name="us-gaap:Revenues" contextRef="product">70</ix:nonFraction></td></tr>
    <tr><td>Alpha</td><td><ix:nonFraction name="us-gaap:Revenues" contextRef="a">40</ix:nonFraction></td></tr>
    <tr><td>Beta</td><td><ix:nonFraction name="us-gaap:Revenues" contextRef="b">30</ix:nonFraction></td></tr>
    <tr><td>Services</td><td><ix:nonFraction name="us-gaap:Revenues" contextRef="service">30</ix:nonFraction></td></tr>
    <tr><td>Old</td><td><ix:nonFraction name="us-gaap:Revenues" contextRef="old">100</ix:nonFraction></td></tr></table>
    </body></html>"""
    groups = revenue_disaggregations(html, "2026-01-01", "2026-03-31", 100)
    assert len(groups) == 1
    assert {item["label"] for item in groups[0]["items"]} == {"Alpha", "Beta", "Services"}
    assert sum(item["value"] for item in groups[0]["items"]) == 100
    assert revenue_disaggregations(html, "2026-01-01", "2026-03-31", 110) == []


def test_composition_api_validates_filing_form():
    class Service:
        def composition(self, ticker, form, years):
            return {"ticker": ticker, "form": form, "years": years}
    client = TestClient(create_app(service=Service(), token="test-session"))
    headers = {"X-FilingLens-Token": "test-session"}
    assert client.get("/api/company/TEST/composition?form=10-Q", headers=headers).json() == {
        "ticker": "TEST", "form": "10-Q", "years": 5,
    }
    assert client.get("/api/company/TEST/composition?form=8-K", headers=headers).status_code == 422
