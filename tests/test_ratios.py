from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from filinglens.analytics.normalize import financials_wide
from filinglens.analytics.ratios import calculate_ratios
from filinglens.analytics.trends import year_over_year_changes
from filinglens.sec.xbrl import select_annual_facts


def test_wide_financials_and_free_cash_flow(company_facts_payload):
    wide = financials_wide(select_annual_facts(company_facts_payload, "EXM"))
    assert wide.loc[2024, "free_cash_flow"] == 23


def test_revenue_growth_uses_absolute_prior_denominator():
    financials = pd.DataFrame({"revenue": [100.0, 120.0]}, index=pd.Index([2023, 2024], name="fiscal_year"))
    ratios = calculate_ratios(financials)
    assert ratios.loc[2024, "revenue_growth"] == pytest.approx(0.2)
    assert pd.isna(ratios.loc[2023, "revenue_growth"])


def test_profitability_and_cash_flow_margins():
    frame = pd.DataFrame(
        {"revenue": [200.0], "gross_profit": [80.0], "operating_income": [40.0], "net_income": [20.0], "operating_cash_flow": [30.0], "free_cash_flow": [25.0]},
        index=pd.Index([2024], name="fiscal_year"),
    )
    ratios = calculate_ratios(frame)
    assert ratios.loc[2024, "gross_margin"] == 0.4
    assert ratios.loc[2024, "operating_margin"] == 0.2
    assert ratios.loc[2024, "net_margin"] == 0.1
    assert ratios.loc[2024, "free_cash_flow_margin"] == 0.125


def test_liquidity_and_leverage():
    frame = pd.DataFrame(
        {"current_assets": [120.0], "current_liabilities": [60.0], "long_term_debt": [50.0], "total_assets": [200.0], "stockholders_equity": [100.0]},
        index=pd.Index([2024], name="fiscal_year"),
    )
    ratios = calculate_ratios(frame)
    assert ratios.loc[2024, "current_ratio"] == 2
    assert ratios.loc[2024, "debt_to_assets"] == 0.25
    assert ratios.loc[2024, "debt_to_equity"] == 0.5


def test_divide_by_zero_returns_missing():
    frame = pd.DataFrame(
        {"revenue": [0.0], "net_income": [10.0], "current_assets": [5.0], "current_liabilities": [0.0]},
        index=pd.Index([2024], name="fiscal_year"),
    )
    ratios = calculate_ratios(frame)
    assert pd.isna(ratios.loc[2024, "net_margin"])
    assert pd.isna(ratios.loc[2024, "current_ratio"])


def test_negative_equity_keeps_mathematically_defined_ratio():
    frame = pd.DataFrame(
        {"long_term_debt": [50.0], "stockholders_equity": [-25.0]},
        index=pd.Index([2024], name="fiscal_year"),
    )
    assert calculate_ratios(frame).loc[2024, "debt_to_equity"] == -2


def test_return_ratios_use_average_balances():
    frame = pd.DataFrame(
        {"net_income": [10.0, 12.0], "total_assets": [100.0, 140.0], "stockholders_equity": [50.0, 70.0]},
        index=pd.Index([2023, 2024], name="fiscal_year"),
    )
    ratios = calculate_ratios(frame)
    assert ratios.loc[2024, "return_on_assets"] == pytest.approx(0.1)
    assert ratios.loc[2024, "return_on_equity"] == pytest.approx(0.2)


def test_missing_input_does_not_create_ratio():
    frame = pd.DataFrame({"net_income": [1.0]}, index=pd.Index([2024], name="fiscal_year"))
    assert "net_margin" not in calculate_ratios(frame)


def test_year_over_year_change_values():
    frame = pd.DataFrame({"revenue": [100.0, 130.0]}, index=[2023, 2024])
    result = year_over_year_changes(frame).iloc[0]
    assert result["absolute_change"] == 30
    assert result["percentage_change"] == pytest.approx(0.3)

