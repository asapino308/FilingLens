"""Year-over-year change calculations for financial series."""

from __future__ import annotations

import numpy as np
import pandas as pd


def year_over_year_changes(values: pd.DataFrame) -> pd.DataFrame:
    """Return absolute and percent changes for every numeric metric."""
    records: list[dict[str, float | int | str]] = []
    for metric in values.columns:
        series = values[metric].dropna().sort_index()
        items = list(series.items())
        for (prior_period, prior), (period, current) in zip(items, items[1:]):
            absolute = float(current - prior)
            percentage = np.nan if prior == 0 else float(absolute / abs(prior))
            records.append(
                {
                    "metric": metric,
                    "period": int(period),
                    "prior_period": int(prior_period),
                    "prior_value": float(prior),
                    "current_value": float(current),
                    "absolute_change": absolute,
                    "percentage_change": percentage,
                }
            )
    return pd.DataFrame(records)
