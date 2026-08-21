"""Reusable formatting for deterministic values and evidence."""

from __future__ import annotations

from collections.abc import MutableMapping
import pandas as pd


LABELS = {
    "revenue": "Revenue",
    "gross_profit": "Gross profit",
    "operating_income": "Operating income",
    "net_income": "Net income",
    "operating_cash_flow": "Operating cash flow",
    "free_cash_flow": "Free cash flow",
    "total_assets": "Total assets",
    "long_term_debt": "Long-term debt",
}

ANOMALY_COLOR_MODES = (
    "Likely financial impact",
    "Raw increase / decrease",
    "Off",
)

LIKELY_DIRECTION_ORDER = (
    "Strongly favorable",
    "Moderately favorable",
    "Lightly favorable",
    "Lightly unfavorable",
    "Moderately unfavorable",
    "Strongly unfavorable",
)

RAW_DIRECTION_ORDER = (
    "Strong gain",
    "Moderate gain",
    "Light gain",
    "Light loss",
    "Moderate loss",
    "Strong loss",
)

_LOWER_IS_BETTER_FRAGMENTS = (
    "cost",
    "expense",
    "debt",
    "liability",
    "liabilities",
)

_MULTIPLE_RATIO_METRICS = {"current_ratio", "debt_to_equity"}

AI_SESSION_KEYS = (
    "retrieval",
    "sections",
    "retrieval_accession",
    "retrieval_ticker",
    "analyst_brief",
    "analyst_brief_key",
    "insider_activity",
    "insider_activity_key",
)


def human_currency(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "Unavailable"
    sign = "-" if value < 0 else ""
    absolute = abs(float(value))
    for divisor, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if absolute >= divisor:
            return f"{sign}${absolute / divisor:,.2f}{suffix}"
    return f"{sign}${absolute:,.0f}"


def anomaly_change_presentation(
    metric: str, percentage_change: float | int | None, color_mode: str
) -> tuple[str, float | None]:
    """Return a readable direction label and signed value used for color intensity."""
    if color_mode not in ANOMALY_COLOR_MODES:
        raise ValueError(f"Unknown anomaly color mode: {color_mode}")
    if percentage_change is None or pd.isna(percentage_change):
        return "Unavailable", None

    change = float(percentage_change)
    if change == 0:
        return "No change", 0.0

    if color_mode == "Likely financial impact":
        normalized_metric = metric.lower().replace(" ", "_")
        lower_is_better = any(
            fragment in normalized_metric for fragment in _LOWER_IS_BETTER_FRAGMENTS
        )
        color_value = -change if lower_is_better else change
        direction = "favorable" if color_value > 0 else "unfavorable"
    else:
        color_value = change
        direction = "gain" if change > 0 else "loss"

    magnitude = abs(change)
    if magnitude >= 0.40:
        degree = "Strongly" if color_mode == "Likely financial impact" else "Strong"
    elif magnitude >= 0.20:
        degree = "Moderately" if color_mode == "Likely financial impact" else "Moderate"
    else:
        degree = "Lightly" if color_mode == "Likely financial impact" else "Light"
    return f"{degree} {direction}", color_value


def anomaly_color_css(color_value: float | None) -> str:
    """Map signed movement to accessible light, medium, or deep green/red styling."""
    if color_value is None or pd.isna(color_value) or color_value == 0:
        return ""
    magnitude = abs(float(color_value))
    if color_value > 0:
        if magnitude >= 0.40:
            background, foreground = "#146B3A", "#FFFFFF"
        elif magnitude >= 0.20:
            background, foreground = "#62B77A", "#092B15"
        else:
            background, foreground = "#DDF4E4", "#123C20"
    elif magnitude >= 0.40:
        background, foreground = "#9E2636", "#FFFFFF"
    elif magnitude >= 0.20:
        background, foreground = "#E17880", "#3E0C11"
    else:
        background, foreground = "#F8DDE0", "#4A1118"
    return f"background-color: {background}; color: {foreground}; font-weight: 700"


def _anomaly_value_text(metric: str, value: float | int | None, *, change: bool) -> str:
    if value is None or pd.isna(value):
        return "—"
    numeric = float(value)
    if metric in _MULTIPLE_RATIO_METRICS:
        return f"{numeric:+.2f}x" if change else f"{numeric:.2f}x"
    if (
        metric.endswith("_growth")
        or metric.endswith("_margin")
        or metric.startswith("return_on_")
        or metric == "debt_to_assets"
    ):
        return f"{numeric * 100:+.1f} pp" if change else f"{numeric:.1%}"
    text = human_currency(numeric)
    return f"+{text}" if change and numeric > 0 else text


def anomaly_display_table(frame: pd.DataFrame, color_mode: str):
    """Build a compact anomaly table with optional magnitude-aware cell coloring."""
    columns = [
        "Metric",
        "Period",
        "Prior",
        "Current",
        "Absolute change",
        "Change",
        "Direction",
        "Severity",
        "Robust score",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns).style

    display_rows: list[dict[str, object]] = []
    color_values: list[float | None] = []
    direction_order = (
        LIKELY_DIRECTION_ORDER
        if color_mode == "Likely financial impact"
        else RAW_DIRECTION_ORDER
    )
    for _, row in frame.iterrows():
        change = row.get("percentage_change")
        direction, color_value = anomaly_change_presentation(
            str(row["metric"]), change, color_mode
        )
        direction_rank = direction_order.index(direction) + 1 if direction in direction_order else 7
        color_values.append(color_value)
        metric = str(row["metric"])
        display_rows.append(
            {
                "Metric": metric.replace("_", " ").title(),
                "Period": int(row["period"]),
                "Prior": _anomaly_value_text(metric, row.get("prior_value"), change=False),
                "Current": _anomaly_value_text(
                    metric, row.get("current_value"), change=False
                ),
                "Absolute change": _anomaly_value_text(
                    metric, row.get("absolute_change"), change=True
                ),
                "Change": "—" if pd.isna(change) else f"{float(change):+.1%}",
                "Direction": f"{direction_rank} · {direction}",
                "Severity": row["severity"],
                "Robust score": (
                    "—"
                    if pd.isna(row.get("anomaly_score"))
                    else f"{float(row['anomaly_score']):+.2f}"
                ),
            }
        )

    display = pd.DataFrame(display_rows, columns=columns)
    styles = pd.DataFrame("", index=display.index, columns=display.columns)
    if color_mode != "Off":
        for position, color_value in enumerate(color_values):
            css = anomaly_color_css(color_value)
            styles.iloc[position, display.columns.get_loc("Change")] = css
            styles.iloc[position, display.columns.get_loc("Direction")] = css
    return display.style.apply(lambda _: styles, axis=None)


def verified_metrics_text(financials: pd.DataFrame, ratios: pd.DataFrame) -> str:
    if financials.empty:
        return "No verified financial metrics are available."
    lines: list[str] = []
    years = list(financials.index[-2:])
    for year in years:
        for metric in ("revenue", "operating_income", "net_income", "operating_cash_flow", "free_cash_flow"):
            if metric in financials and pd.notna(financials.loc[year, metric]):
                lines.append(f"{LABELS.get(metric, metric)} FY{year}: {human_currency(financials.loc[year, metric])}")
        for ratio in ("revenue_growth", "operating_margin", "net_margin", "current_ratio", "debt_to_equity"):
            if ratio in ratios and year in ratios.index and pd.notna(ratios.loc[year, ratio]):
                value = float(ratios.loc[year, ratio])
                formatted = f"{value:.2f}x" if ratio in {"current_ratio", "debt_to_equity"} else f"{value:.2%}"
                lines.append(f"{ratio.replace('_', ' ').title()} FY{year}: {formatted}")
    return "\n".join(lines) or "No verified financial metrics are available."


def anomaly_summary_text(frame: pd.DataFrame, limit: int = 12) -> str:
    """Create a compact, deterministic anomaly context for local generation."""
    if frame.empty:
        return "No notable flags."
    if limit < 1:
        raise ValueError("limit must be at least 1")

    ranked = frame.copy()
    ranked["_severity_rank"] = ranked["severity"].map(
        {"Significant": 0, "Notable": 1, "Normal": 2}
    ).fillna(3)
    ranked["_magnitude"] = pd.to_numeric(
        ranked["percentage_change"], errors="coerce"
    ).abs().fillna(-1)
    ranked = ranked.sort_values(
        ["_severity_rank", "_magnitude", "period"],
        ascending=[True, False, False],
    )

    lines: list[str] = []
    for _, row in ranked.head(limit).iterrows():
        metric = str(row["metric"]).replace("_", " ").title()
        percentage = row.get("percentage_change")
        change = "change unavailable" if pd.isna(percentage) else f"{float(percentage):+.1%}"
        score = row.get("anomaly_score")
        score_text = "" if pd.isna(score) else f"; robust score {float(score):+.2f}"
        lines.append(
            f"- {metric} FY{int(row['period'])}: {change} "
            f"({row['severity']}{score_text})"
        )

    omitted = len(ranked) - len(lines)
    if omitted > 0:
        lines.append(f"- {omitted} additional flagged movement(s) omitted for prompt efficiency.")
    return "\n".join(lines)


def synchronize_filing_session(
    state: MutableMapping[str, object], filing_key: str
) -> bool:
    """Clear filing-specific AI state when the active company filing changes."""
    if state.get("active_filing_key") == filing_key:
        return False
    for key in AI_SESSION_KEYS:
        state.pop(key, None)
    state["active_filing_key"] = filing_key
    return True


def format_ratio_table(frame: pd.DataFrame) -> pd.DataFrame:
    formatted = frame.copy()
    for column in formatted.columns:
        if column not in {"current_ratio", "debt_to_equity"}:
            formatted[column] = formatted[column].map(
                lambda value: "—" if pd.isna(value) else f"{value:.1%}"
            )
        else:
            formatted[column] = formatted[column].map(
                lambda value: "—" if pd.isna(value) else f"{value:.2f}x"
            )
    return formatted
