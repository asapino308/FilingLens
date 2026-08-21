"""Safe SEC HTML-to-text parsing."""

from __future__ import annotations

import html
import re
import warnings

from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning


def clean_filing_html(document: str) -> str:
    """Remove active/boilerplate elements and normalize visible filing text."""
    if not document or not document.strip():
        return ""
    # Inline XBRL filings are HTML documents with XML declarations; HTML parsing
    # is intentional because it preserves visible SEC filing content.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(document, "lxml")
    for element in soup(["script", "style", "noscript", "svg", "nav"]):
        element.decompose()
    text = soup.get_text("\n")
    text = html.unescape(text).replace("\xa0", " ")
    lines: list[str] = []
    previous = ""
    for raw in text.splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if len(line) < 2 or line == previous:
            continue
        lines.append(line)
        previous = line
    return "\n".join(lines)
