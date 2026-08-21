"""Restrained Plotly charts for financial trends."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


COLORS = ["#0B4F6C", "#01BAEF", "#6C8EAD", "#F4A261", "#2A9D8F"]


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

