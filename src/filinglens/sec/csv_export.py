"""Export SEC-supplied text as literal spreadsheet cells."""

from __future__ import annotations

import pandas as pd


def safe_csv_cell(value: object) -> object:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def safe_csv(frame: pd.DataFrame) -> str:
    exported = frame.copy()
    for column in exported.select_dtypes(include=["object", "string"]).columns:
        exported[column] = exported[column].map(safe_csv_cell)
    return exported.to_csv(index=False)
