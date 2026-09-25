"""Reusable formatting for deterministic values and evidence."""

from __future__ import annotations

from collections.abc import MutableMapping
import pandas as pd


LABELS = {
    "revenue": "Revenue",
    "cost_of_revenue": "Cost of revenue",
    "gross_profit": "Gross profit",
    "operating_income": "Operating income",
    "net_income": "Net income",
    "cash": "Cash and cash equivalents",
    "current_assets": "Current assets",
    "operating_cash_flow": "Operating cash flow",
    "capital_expenditures": "Capital expenditures",
    "free_cash_flow": "Free cash flow",
    "total_assets": "Total assets",
    "current_liabilities": "Current liabilities",
    "total_liabilities": "Total liabilities",
    "stockholders_equity": "Stockholders' equity",
    "long_term_debt": "Long-term debt",
    "revenue_growth": "Revenue growth",
    "operating_income_growth": "Operating income growth",
    "net_income_growth": "Net income growth",
    "operating_cash_flow_growth": "Operating cash flow growth",
    "free_cash_flow_growth": "Free cash flow growth",
    "gross_margin": "Gross margin",
    "operating_margin": "Operating margin",
    "net_margin": "Net margin",
    "operating_cash_flow_margin": "Operating cash flow margin",
    "free_cash_flow_margin": "Free cash flow margin",
    "return_on_assets": "Return on assets",
    "return_on_equity": "Return on equity",
    "current_ratio": "Current ratio",
    "debt_to_assets": "Debt to assets",
    "debt_to_equity": "Debt to equity",
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

METRIC_FORMULAS = {
    "gross_profit": "Revenue − cost of revenue",
    "free_cash_flow": "Operating cash flow − capital expenditures",
    "revenue_growth": "Change in revenue ÷ absolute prior-year revenue",
    "operating_income_growth": "Change in operating income ÷ absolute prior-year operating income",
    "net_income_growth": "Change in net income ÷ absolute prior-year net income",
    "operating_cash_flow_growth": "Change in operating cash flow ÷ absolute prior-year operating cash flow",
    "free_cash_flow_growth": "Change in free cash flow ÷ absolute prior-year free cash flow",
    "gross_margin": "Gross profit ÷ revenue",
    "operating_margin": "Operating income ÷ revenue",
    "net_margin": "Net income ÷ revenue",
    "operating_cash_flow_margin": "Operating cash flow ÷ revenue",
    "free_cash_flow_margin": "Free cash flow ÷ revenue",
    "return_on_assets": "Net income ÷ average total assets",
    "return_on_equity": "Net income ÷ average stockholders' equity",
    "current_ratio": "Current assets ÷ current liabilities",
    "debt_to_assets": "Long-term debt ÷ total assets",
    "debt_to_equity": "Long-term debt ÷ stockholders' equity",
}

_FORMULA_COMPONENTS = {
    "gross_profit": ("revenue", "cost_of_revenue"),
    "free_cash_flow": ("operating_cash_flow", "capital_expenditures"),
    "gross_margin": ("gross_profit", "revenue"),
    "operating_margin": ("operating_income", "revenue"),
    "net_margin": ("net_income", "revenue"),
    "operating_cash_flow_margin": ("operating_cash_flow", "revenue"),
    "free_cash_flow_margin": ("free_cash_flow", "revenue"),
    "current_ratio": ("current_assets", "current_liabilities"),
    "debt_to_assets": ("long_term_debt", "total_assets"),
    "debt_to_equity": ("long_term_debt", "stockholders_equity"),
}

_GROWTH_SOURCES = {
    "revenue_growth": "revenue",
    "operating_income_growth": "operating_income",
    "net_income_growth": "net_income",
    "operating_cash_flow_growth": "operating_cash_flow",
    "free_cash_flow_growth": "free_cash_flow",
}

AI_SESSION_KEYS = (
    "retrieval",
    "sections",
    "retrieval_accession",
    "retrieval_ticker",
    "analyst_brief",
    "analyst_brief_key",
    "insider_activity",
    "insider_activity_key",
    "overview_answer",
    "overview_answer_key",
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


def period_delta(frame: pd.DataFrame, metric: str) -> str | None:
    """Format the latest year-over-year movement for a headline metric."""
    if metric not in frame or len(frame.index) < 2:
        return None
    series = pd.to_numeric(frame[metric], errors="coerce").dropna()
    if len(series) < 2:
        return None
    prior = float(series.iloc[-2])
    current = float(series.iloc[-1])
    if prior == 0:
        return None
    change = (current - prior) / abs(prior)
    return f"{change:+.1%} vs FY{int(series.index[-2])}"


def ratio_display(metric: str, value: float | int | None) -> str:
    """Format a ratio snapshot using either percentage or multiple units."""
    if value is None or pd.isna(value):
        return "Unavailable"
    numeric = float(value)
    if metric in _MULTIPLE_RATIO_METRICS:
        return f"{numeric:.2f}x"
    return f"{numeric:.1%}"


def metric_display_value(
    metric: str, value: float | int | None, *, ratio: bool = False
) -> str:
    """Format one statement or ratio value for a human-readable trend table."""
    if value is None or pd.isna(value):
        return "—"
    if ratio:
        return ratio_display(metric, value)
    return human_currency(value)


def metric_latest_change(
    frame: pd.DataFrame, metric: str, *, ratio: bool = False
) -> str:
    """Describe the latest comparable movement using the metric's natural unit."""
    if metric not in frame.columns:
        return "—"
    series = pd.to_numeric(frame[metric], errors="coerce").dropna()
    if len(series) < 2:
        return "—"
    prior = float(series.iloc[-2])
    current = float(series.iloc[-1])
    if ratio:
        difference = current - prior
        if metric in _MULTIPLE_RATIO_METRICS:
            return f"{difference:+.2f}x"
        return f"{difference * 100:+.1f} pp"
    if prior == 0:
        return "—"
    return f"{(current - prior) / abs(prior):+.1%}"


def metric_trend_table(
    frame: pd.DataFrame, metrics: list[str] | tuple[str, ...], *, ratio: bool = False
) -> pd.DataFrame:
    """Create account rows with sparklines, readable annual values, and latest movement."""
    year_columns = [f"FY{int(year)}" for year in frame.index]
    columns = ["_metric", "Account", "Trend", *year_columns, "Latest change"]
    if frame.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    for metric in metrics:
        if metric not in frame.columns:
            continue
        numeric = pd.to_numeric(frame[metric], errors="coerce")
        if not numeric.notna().any():
            continue
        row: dict[str, object] = {
            "_metric": metric,
            "Account": LABELS.get(metric, metric.replace("_", " ").title()),
            # LineChartColumn displays its raw fallback value when an array starts
            # with null. Growth and return series naturally have an unavailable
            # first year, so omit missing points from the compact sparkline.
            "Trend": [float(value) for value in numeric if pd.notna(value)],
            "Latest change": metric_latest_change(frame, metric, ratio=ratio),
        }
        for year, value in numeric.items():
            row[f"FY{int(year)}"] = metric_display_value(metric, value, ratio=ratio)
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def metric_component_table(
    financials: pd.DataFrame, metric: str, fiscal_year: int
) -> pd.DataFrame:
    """Return transparent inputs for derived accounts and ratios when available."""
    columns = ["Component", f"FY{int(fiscal_year)} value"]
    if financials.empty or fiscal_year not in financials.index:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, str]] = []

    def add_component(label: str, value: float | int | None) -> None:
        if value is not None and not pd.isna(value):
            rows.append(
                {
                    "Component": label,
                    f"FY{int(fiscal_year)} value": human_currency(value),
                }
            )

    if metric in _FORMULA_COMPONENTS:
        for component in _FORMULA_COMPONENTS[metric]:
            value = (
                financials.loc[fiscal_year, component]
                if component in financials.columns
                else None
            )
            label = LABELS.get(component, component.replace("_", " ").title())
            if metric in {"gross_profit", "free_cash_flow"} and component in {
                "cost_of_revenue",
                "capital_expenditures",
            }:
                label = f"Less: {label}"
            add_component(label, value)
    elif metric in _GROWTH_SOURCES:
        source = _GROWTH_SOURCES[metric]
        source_series = (
            pd.to_numeric(financials[source], errors="coerce").dropna()
            if source in financials.columns
            else pd.Series(dtype=float)
        )
        if fiscal_year in source_series.index:
            position = list(source_series.index).index(fiscal_year)
            add_component(
                f"Current {LABELS.get(source, source)}", source_series.loc[fiscal_year]
            )
            if position > 0:
                prior_year = int(source_series.index[position - 1])
                add_component(
                    f"Prior {LABELS.get(source, source)} (FY{prior_year})",
                    source_series.iloc[position - 1],
                )
    elif metric in {"return_on_assets", "return_on_equity"}:
        denominator = (
            "total_assets" if metric == "return_on_assets" else "stockholders_equity"
        )
        add_component(
            "Net income",
            financials.loc[fiscal_year, "net_income"]
            if "net_income" in financials.columns
            else None,
        )
        denominator_series = (
            pd.to_numeric(financials[denominator], errors="coerce")
            if denominator in financials.columns
            else pd.Series(dtype=float)
        )
        if fiscal_year in denominator_series.index:
            location = list(denominator_series.index).index(fiscal_year)
            if location > 0:
                prior = denominator_series.iloc[location - 1]
                current = denominator_series.loc[fiscal_year]
                if pd.notna(prior) and pd.notna(current):
                    add_component(
                        f"Average {LABELS.get(denominator, denominator).lower()}",
                        (float(prior) + float(current)) / 2,
                    )
    return pd.DataFrame(rows, columns=columns)


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
