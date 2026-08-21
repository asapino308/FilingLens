from __future__ import annotations

import pandas as pd
import pytest

from filinglens.ui.components import (
    anomaly_change_presentation,
    anomaly_color_css,
    anomaly_display_table,
    anomaly_summary_text,
    synchronize_filing_session,
)


def test_anomaly_summary_is_compact_and_prioritized():
    frame = pd.DataFrame(
        [
            {
                "metric": "revenue",
                "period": 2025,
                "percentage_change": 0.25,
                "anomaly_score": 2.6,
                "severity": "Notable",
                "explanation": "x" * 5_000,
            },
            {
                "metric": "free_cash_flow",
                "period": 2025,
                "percentage_change": -0.55,
                "anomaly_score": 4.2,
                "severity": "Significant",
                "explanation": "y" * 5_000,
            },
        ]
    )

    summary = anomaly_summary_text(frame, limit=1)

    assert summary.startswith("- Free Cash Flow FY2025: -55.0% (Significant")
    assert "1 additional flagged movement" in summary
    assert len(summary) < 250


def test_anomaly_summary_validates_limit():
    with pytest.raises(ValueError, match="at least 1"):
        anomaly_summary_text(pd.DataFrame([{"severity": "Notable"}]), limit=0)


@pytest.mark.parametrize(
    ("metric", "change", "expected_label", "expected_sign"),
    [
        ("revenue", 0.10, "Lightly favorable", 1),
        ("revenue", 0.25, "Moderately favorable", 1),
        ("revenue", 0.50, "Strongly favorable", 1),
        ("revenue", -0.10, "Lightly unfavorable", -1),
        ("cost_of_revenue", 0.25, "Moderately unfavorable", -1),
        ("long_term_debt", -0.50, "Strongly favorable", 1),
    ],
)
def test_anomaly_change_presentation_reflects_magnitude_and_financial_direction(
    metric: str, change: float, expected_label: str, expected_sign: int
):
    label, color_value = anomaly_change_presentation(
        metric, change, "Likely financial impact"
    )
    assert label == expected_label
    assert color_value is not None
    assert (color_value > 0) is (expected_sign > 0)


def test_raw_change_mode_does_not_invert_cost_increases():
    label, color_value = anomaly_change_presentation(
        "cost_of_revenue", 0.50, "Raw increase / decrease"
    )
    assert label == "Strong gain"
    assert color_value == pytest.approx(0.50)


def test_anomaly_colors_deepen_with_magnitude():
    light_green = anomaly_color_css(0.10)
    deep_green = anomaly_color_css(0.50)
    light_red = anomaly_color_css(-0.10)
    deep_red = anomaly_color_css(-0.50)
    assert "#DDF4E4" in light_green
    assert "#146B3A" in deep_green
    assert "#F8DDE0" in light_red
    assert "#9E2636" in deep_red


def test_anomaly_display_table_is_compact_and_omits_truncated_explanation():
    frame = pd.DataFrame(
        [
            {
                "metric": "revenue",
                "period": 2025,
                "prior_value": 100_000_000,
                "current_value": 150_000_000,
                "absolute_change": 50_000_000,
                "percentage_change": 0.50,
                "anomaly_score": 3.8,
                "severity": "Significant",
                "method": "YoY economic change",
                "explanation": "A complete explanation that belongs below the table.",
            }
        ]
    )
    styled = anomaly_display_table(frame, "Likely financial impact")
    assert "explanation" not in {str(column).lower() for column in styled.data.columns}
    assert styled.data.loc[0, "Prior"] == "$100.00M"
    assert styled.data.loc[0, "Absolute change"] == "+$50.00M"
    assert styled.data.loc[0, "Direction"] == "1 · Strongly favorable"


def test_anomaly_direction_has_a_stable_ascending_and_descending_sort_rank():
    changes = [0.50, 0.25, 0.10, -0.10, -0.25, -0.50]
    frame = pd.DataFrame(
        [
            {
                "metric": "revenue",
                "period": 2025 - index,
                "prior_value": 100,
                "current_value": 100 * (1 + change),
                "absolute_change": 100 * change,
                "percentage_change": change,
                "anomaly_score": 0,
                "severity": "Normal",
            }
            for index, change in enumerate(changes)
        ]
    )
    direction = anomaly_display_table(frame, "Likely financial impact").data["Direction"]
    assert list(direction) == [
        "1 · Strongly favorable",
        "2 · Moderately favorable",
        "3 · Lightly favorable",
        "4 · Lightly unfavorable",
        "5 · Moderately unfavorable",
        "6 · Strongly unfavorable",
    ]
    assert list(direction.sort_values()) == list(direction)
    assert list(direction.sort_values(ascending=False)) == list(reversed(direction))


def test_anomaly_display_table_formats_ratio_units():
    frame = pd.DataFrame(
        [
            {
                "metric": "operating_margin",
                "period": 2025,
                "prior_value": 0.20,
                "current_value": 0.25,
                "absolute_change": 0.05,
                "percentage_change": 0.25,
                "anomaly_score": 2.7,
                "severity": "Notable",
            },
            {
                "metric": "current_ratio",
                "period": 2025,
                "prior_value": 1.20,
                "current_value": 1.50,
                "absolute_change": 0.30,
                "percentage_change": 0.25,
                "anomaly_score": 2.7,
                "severity": "Notable",
            },
        ]
    )
    display = anomaly_display_table(frame, "Raw increase / decrease").data
    assert display.loc[0, "Prior"] == "20.0%"
    assert display.loc[0, "Absolute change"] == "+5.0 pp"
    assert display.loc[1, "Prior"] == "1.20x"
    assert display.loc[1, "Absolute change"] == "+0.30x"


def test_filing_session_state_is_cleared_on_ticker_or_accession_change():
    state = {
        "active_filing_key": "AAPL:old",
        "retrieval": object(),
        "retrieval_ticker": "AAPL",
        "retrieval_accession": "old",
        "analyst_brief": "Old brief",
        "unrelated": "keep",
    }

    changed = synchronize_filing_session(state, "AMZN:new")

    assert changed is True
    assert state == {"active_filing_key": "AMZN:new", "unrelated": "keep"}
    assert synchronize_filing_session(state, "AMZN:new") is False
