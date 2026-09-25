"""Restrained Plotly charts for financial trends."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


COLORS = ["#0B4F6C", "#01BAEF", "#6C8EAD", "#F4A261", "#2A9D8F"]


def account_trend_chart(
    frame: pd.DataFrame,
    metric: str,
    label: str,
    *,
    ratio: bool = False,
    multiple: bool = False,
) -> go.Figure:
    """Build a focused account chart for row-level financial-statement drill-down."""
    if metric not in frame.columns:
        return go.Figure().update_layout(title="No reliable mapped data available")
    series = pd.to_numeric(frame[metric], errors="coerce")
    values = series if not ratio or multiple else series * 100
    hover_template = (
        "%{y:.2f}x"
        if multiple
        else "%{y:.1f}%"
        if ratio
        else "$%{y:,.0f}"
    )
    figure = go.Figure(
        go.Scatter(
            x=[int(year) for year in series.index],
            y=values,
            mode="lines+markers",
            line={"color": "#2A9D8F", "width": 3},
            marker={"size": 8},
            fill="tozeroy",
            fillcolor="rgba(42, 157, 143, 0.12)",
            hovertemplate=f"FY%{{x}}<br>{label}: {hover_template}<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_white",
        title=label,
        showlegend=False,
        height=310,
        margin={"l": 25, "r": 15, "t": 55, "b": 30},
        xaxis={"title": "Fiscal year", "dtick": 1},
        yaxis={
            "title": "Multiple" if multiple else "Percent" if ratio else "USD",
            "ticksuffix": "x" if multiple else "%" if ratio else "",
            "tickformat": ".2f" if multiple else ".1f" if ratio else "~s",
            "zeroline": True,
            "zerolinecolor": "#9CA3AF",
        },
        hovermode="x unified",
    )
    return figure


def financial_trend_chart(frame: pd.DataFrame, metrics: list[str], title: str) -> go.Figure:
    selected = [metric for metric in metrics if metric in frame.columns]
    if not selected:
        return go.Figure().update_layout(title="No reliable mapped data available")
    plot_frame = frame[selected].reset_index().melt(
        id_vars="fiscal_year", var_name="Metric", value_name="Value"
    )
    figure = px.line(
        plot_frame,
        x="fiscal_year",
        y="Value",
        color="Metric",
        markers=True,
        title=title,
        color_discrete_sequence=COLORS,
    )
    figure.update_layout(
        template="plotly_white",
        legend_title_text="",
        yaxis_tickformat="~s",
        xaxis_title="Fiscal year",
        yaxis_title="USD",
        hovermode="x unified",
    )
    return figure


def ratio_trend_chart(ratios: pd.DataFrame, metrics: list[str], title: str) -> go.Figure:
    selected = [metric for metric in metrics if metric in ratios.columns]
    if not selected:
        return go.Figure().update_layout(title="No reliable ratio data available")
    plot_frame = (ratios[selected] * 100).reset_index().melt(
        id_vars="fiscal_year", var_name="Metric", value_name="Percent"
    )
    figure = px.line(
        plot_frame,
        x="fiscal_year",
        y="Percent",
        color="Metric",
        markers=True,
        title=title,
        color_discrete_sequence=COLORS,
    )
    figure.update_layout(
        template="plotly_white",
        legend_title_text="",
        yaxis_ticksuffix="%",
        xaxis_title="Fiscal year",
        hovermode="x unified",
    )
    return figure
