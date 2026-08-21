"""Financial statement normalization helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


def financials_wide(facts: pd.DataFrame) -> pd.DataFrame:
    """Pivot provenance-rich long facts to one row per fiscal year."""
    if facts.empty:
        return pd.DataFrame()
    wide = facts.pivot_table(
        index="fiscal_year", columns="metric", values="value", aggfunc="first"
    ).sort_index()
    if {"operating_cash_flow", "capital_expenditures"}.issubset(wide.columns):
        wide["free_cash_flow"] = wide["operating_cash_flow"] - wide["capital_expenditures"]
    if "gross_profit" not in wide and {"revenue", "cost_of_revenue"}.issubset(wide.columns):
        wide["gross_profit"] = wide["revenue"] - wide["cost_of_revenue"]
    return wide.replace([np.inf, -np.inf], np.nan)


STATEMENT_METRICS = {
    "Income Statement": [
        "revenue",
        "cost_of_revenue",
        "gross_profit",
        "operating_income",
        "net_income",
    ],
    "Balance Sheet": [
        "cash",
        "current_assets",
        "total_assets",
        "current_liabilities",
        "total_liabilities",
        "stockholders_equity",
        "long_term_debt",
    ],
    "Cash Flow": ["operating_cash_flow", "capital_expenditures", "free_cash_flow"],
}


def statement_table(wide: pd.DataFrame, statement: str) -> pd.DataFrame:
    metrics = [metric for metric in STATEMENT_METRICS[statement] if metric in wide.columns]
    return wide[metrics].T if metrics else pd.DataFrame()

