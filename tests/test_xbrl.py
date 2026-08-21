from __future__ import annotations

import pandas as pd

from filinglens.sec.xbrl import METRIC_DEFINITIONS, select_annual_facts

from conftest import make_fact


def test_candidate_mapping_has_core_metrics():
    assert {"revenue", "net_income", "total_assets", "operating_cash_flow"}.issubset(
        METRIC_DEFINITIONS
    )


def test_annual_facts_are_normalized(company_facts_payload):
    frame = select_annual_facts(company_facts_payload, "EXM")
    assert set(frame["metric"]) >= {"revenue", "net_income", "total_assets"}
    assert frame["ticker"].eq("EXM").all()
    assert frame["cik"].eq("0000123456").all()
    assert frame["accession_number"].str.len().gt(0).all()


def test_quarterly_duration_is_excluded(company_facts_payload):
    quarterly = make_fact(50, 2024, start="2024-10-01", form="10-K", fp="FY")
    company_facts_payload["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]["units"]["USD"].append(quarterly)
    frame = select_annual_facts(company_facts_payload, "EXM")
    assert frame.query("metric == 'revenue' and fiscal_year == 2024")["value"].iloc[0] == 150


def test_duplicate_prefers_latest_filing(company_facts_payload):
    revised = make_fact(
        155,
        2024,
        start="2024-01-01",
        filed="2025-03-01",
        form="10-K/A",
        accn="amended",
    )
    company_facts_payload["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]["units"]["USD"].append(revised)
    frame = select_annual_facts(company_facts_payload, "EXM")
    record = frame.query("metric == 'revenue' and fiscal_year == 2024").iloc[0]
    assert record["value"] == 155
    assert record["accession_number"] == "amended"


def test_comparative_fact_uses_observation_period_not_filing_fy(company_facts_payload):
    comparative = make_fact(
        130,
        2025,
        start="2023-01-01",
        end="2023-12-31",
        filed="2026-02-01",
    )
    company_facts_payload["facts"]["us-gaap"][
        "RevenueFromContractWithCustomerExcludingAssessedTax"
    ]["units"]["USD"].append(comparative)
    frame = select_annual_facts(company_facts_payload, "EXM")
    record = frame.query("metric == 'revenue' and fiscal_year == 2023").iloc[0]
    assert record["value"] == 130
    assert not ((frame["metric"] == "revenue") & (frame["fiscal_year"] == 2025)).any()


def test_long_term_debt_does_not_select_current_portion():
    payload = {
        "cik": 1,
        "entityName": "Debt Co",
        "facts": {
            "us-gaap": {
                "LongTermDebtCurrent": {"units": {"USD": [make_fact(10, 2024)]}},
                "LongTermDebtNoncurrent": {"units": {"USD": [make_fact(80, 2024)]}},
            }
        },
    }
    frame = select_annual_facts(payload, "DEBT")
    assert frame.query("metric == 'long_term_debt'")["value"].iloc[0] == 80


def test_concept_priority_beats_lower_priority(company_facts_payload):
    company_facts_payload["facts"]["us-gaap"]["Revenues"] = {
        "units": {"USD": [make_fact(999, 2024, start="2024-01-01", filed="2025-04-01")]}
    }
    frame = select_annual_facts(company_facts_payload, "EXM")
    assert frame.query("metric == 'revenue' and fiscal_year == 2024")["value"].iloc[0] == 150


def test_missing_metrics_remain_absent(company_facts_payload):
    frame = select_annual_facts(company_facts_payload, "EXM")
    assert "gross_profit" not in set(frame["metric"])


def test_year_limit_applies_per_metric(company_facts_payload):
    frame = select_annual_facts(company_facts_payload, "EXM", years=2)
    assert set(frame["fiscal_year"]) == {2023, 2024}


def test_empty_payload_returns_typed_empty_frame():
    frame = select_annual_facts({}, "NONE")
    assert frame.empty
    assert "xbrl_concept" in frame.columns
