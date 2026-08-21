"""Deterministic financial analysis."""

from .anomalies import detect_anomalies
from .normalize import financials_wide
from .ratios import calculate_ratios

__all__ = ["calculate_ratios", "detect_anomalies", "financials_wide"]

