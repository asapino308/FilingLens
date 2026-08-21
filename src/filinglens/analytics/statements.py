"""Presentation-friendly financial statement helpers."""

from __future__ import annotations

import pandas as pd

from .normalize import STATEMENT_METRICS


def build_statements(financials: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        name: financials[[m for m in metrics if m in financials.columns]].copy()
        for name, metrics in STATEMENT_METRICS.items()
    }

