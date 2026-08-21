"""Documented, deterministic financial ratio calculations."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.where(denominator != 0)
    return (numerator / denominator).replace([np.inf, -np.inf], np.nan)


def calculate_ratios(financials: pd.DataFrame) -> pd.DataFrame:
    """Calculate growth, profitability, liquidity, leverage, and cash-flow ratios."""
    if financials.empty:
        return pd.DataFrame(index=financials.index)
    values = financials.sort_index().astype(float)
    result = pd.DataFrame(index=values.index)

    growth_metrics = {
        "revenue": "revenue_growth",
        "operating_income": "operating_income_growth",
        "net_income": "net_income_growth",
        "operating_cash_flow": "operating_cash_flow_growth",
        "free_cash_flow": "free_cash_flow_growth",
    }
    for source, target in growth_metrics.items():
        if source in values:
            prior = values[source].shift(1)
            result[target] = _safe_divide(values[source] - prior, prior.abs())

    for numerator, target in (
        ("gross_profit", "gross_margin"),
        ("operating_income", "operating_margin"),
        ("net_income", "net_margin"),
        ("operating_cash_flow", "operating_cash_flow_margin"),
        ("free_cash_flow", "free_cash_flow_margin"),
    ):
        if numerator in values and "revenue" in values:
            result[target] = _safe_divide(values[numerator], values["revenue"])

    if "net_income" in values and "total_assets" in values:
        average_assets = (values["total_assets"] + values["total_assets"].shift(1)) / 2
        result["return_on_assets"] = _safe_divide(values["net_income"], average_assets)
    if "net_income" in values and "stockholders_equity" in values:
        average_equity = (
            values["stockholders_equity"] + values["stockholders_equity"].shift(1)
        ) / 2
        result["return_on_equity"] = _safe_divide(values["net_income"], average_equity)
    if {"current_assets", "current_liabilities"}.issubset(values.columns):
        result["current_ratio"] = _safe_divide(
            values["current_assets"], values["current_liabilities"]
        )
    if {"long_term_debt", "total_assets"}.issubset(values.columns):
        result["debt_to_assets"] = _safe_divide(
            values["long_term_debt"], values["total_assets"]
        )
    if {"long_term_debt", "stockholders_equity"}.issubset(values.columns):
        result["debt_to_equity"] = _safe_divide(
            values["long_term_debt"], values["stockholders_equity"]
        )
    return result.replace([np.inf, -np.inf], np.nan)

