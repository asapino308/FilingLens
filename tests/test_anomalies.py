from __future__ import annotations

import pandas as pd
import pytest

from filinglens.analytics.anomalies import detect_anomalies, robust_z_scores


def test_robust_score_centers_on_median():
    scores = robust_z_scores(pd.Series([0, 1, 2, 100]))
    assert scores.iloc[-1] > 3.5


def test_zero_mad_returns_missing_scores():
    assert robust_z_scores(pd.Series([1, 1, 1])).isna().all()


def test_economic_change_severity():
    frame = pd.DataFrame({"revenue": [100, 110, 121, 181.5]}, index=[2021, 2022, 2023, 2024])
    result = detect_anomalies(frame)
    assert result.iloc[-1]["severity"] == "Significant"
    assert result.iloc[-1]["percentage_change"] == pytest.approx(0.5)


def test_notable_threshold():
    frame = pd.DataFrame({"revenue": [100, 125]}, index=[2023, 2024])
    assert detect_anomalies(frame).iloc[0]["severity"] == "Notable"


def test_insufficient_history_skips_robust_method():
    frame = pd.DataFrame({"revenue": [100, 110, 120]}, index=[2022, 2023, 2024])
    result = detect_anomalies(frame)
    assert result["anomaly_score"].isna().all()
    assert result["method"].eq("YoY economic change").all()


def test_zero_prior_has_unavailable_percentage():
    frame = pd.DataFrame({"net_income": [0, 10]}, index=[2023, 2024])
    record = detect_anomalies(frame).iloc[0]
    assert pd.isna(record["percentage_change"])
    assert "unavailable" in record["explanation"]


def test_terminology_is_responsible():
    frame = pd.DataFrame({"revenue": [100, 200]}, index=[2023, 2024])
    explanation = detect_anomalies(frame).iloc[0]["explanation"].lower()
    assert "not a finding of fraud" in explanation

