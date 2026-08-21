"""Dependency-light report export."""

from __future__ import annotations

import html
import re


def markdown_to_html(markdown: str, title: str = "FilingLens Analyst Brief") -> str:
    """Convert the brief's limited Markdown subset to a standalone HTML document."""
    body: list[str] = []
    for line in markdown.splitlines():
        escaped = html.escape(line)
        if line.startswith("## "):
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("- "):
            body.append(f"<p>• {html.escape(line[2:])}</p>")
        elif line.strip():
            escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
            body.append(f"<p>{escaped}</p>")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font:16px/1.55 system-ui;max-width:900px;margin:40px auto;padding:0 24px;color:#18202b}}h1,h2{{color:#123b5d}}p{{margin:.6rem 0}}</style>
</head><body>{''.join(body)}</body></html>"""

