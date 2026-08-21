"""Economic movement and robust statistical anomaly detection."""

from __future__ import annotations

import math
import numpy as np
import pandas as pd


ROBUST_Z_NOTABLE = 2.5
ROBUST_Z_SIGNIFICANT = 3.5
ECONOMIC_NOTABLE = 0.20
ECONOMIC_SIGNIFICANT = 0.40


def robust_z_scores(series: pd.Series) -> pd.Series:
    """Median absolute deviation scores, stable against a single large outlier."""
    numeric = pd.to_numeric(series, errors="coerce")
    median = numeric.median()
    mad = (numeric - median).abs().median()
    if pd.isna(mad) or mad == 0:
        return pd.Series(np.nan, index=series.index, dtype=float)
    return 0.6745 * (numeric - median) / mad


def _severity(economic: float, robust: float | None) -> str:
    robust_abs = abs(robust) if robust is not None and not math.isnan(robust) else 0.0
    if economic >= ECONOMIC_SIGNIFICANT or robust_abs >= ROBUST_Z_SIGNIFICANT:
        return "Significant"
    if economic >= ECONOMIC_NOTABLE or robust_abs >= ROBUST_Z_NOTABLE:
        return "Notable"
    return "Normal"


def detect_anomalies(values: pd.DataFrame, min_robust_observations: int = 4) -> pd.DataFrame:
    """Flag movements using absolute YoY magnitude and MAD-based robust scores.

    Percentage changes use the absolute prior-year value as denominator, which
    preserves direction while handling negative comparison periods. Robust scores
    apply to the YoY change series and require at least four observations.
    """
    records: list[dict[str, object]] = []
    for metric in values.columns:
        series = pd.to_numeric(values[metric], errors="coerce").dropna().sort_index()
        changes = series.diff()
        percent = changes / series.shift(1).abs().replace(0, np.nan)
        scores = (
            robust_z_scores(percent)
            if percent.count() >= min_robust_observations
            else pd.Series(np.nan, index=series.index)
        )
        for period in series.index[1:]:
            prior_period = series.index[series.index.get_loc(period) - 1]
            pct = percent.loc[period]
            score = scores.loc[period]
            economic_magnitude = abs(float(pct)) if pd.notna(pct) else 0.0
            severity = _severity(economic_magnitude, float(score) if pd.notna(score) else None)
            methods = ["YoY economic change"]
            if pd.notna(score):
                methods.append("MAD robust z-score")
            pct_label = "unavailable" if pd.isna(pct) else f"{float(pct):+.1%}"
            records.append(
                {
                    "metric": metric,
                    "period": int(period),
                    "prior_value": float(series.loc[prior_period]),
                    "current_value": float(series.loc[period]),
                    "absolute_change": float(changes.loc[period]),
                    "percentage_change": float(pct) if pd.notna(pct) else np.nan,
                    "anomaly_score": float(score) if pd.notna(score) else np.nan,
                    "severity": severity,
                    "method": " + ".join(methods),
                    "explanation": (
                        f"{metric.replace('_', ' ').title()} changed {pct_label} versus "
                        f"the prior annual period. This is an unusual-change screen, not a "
                        "finding of fraud or misconduct."
                    ),
                }
            )
    return pd.DataFrame(records)

