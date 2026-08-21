"""Best-effort SEC filing section recognition with full-text fallback."""

from __future__ import annotations

import re


SECTION_PATTERNS = {
    "Item 1 — Business": r"(?im)^\s*item\s+1[.\s:–—-]+business\b",
    "Item 1A — Risk Factors": r"(?im)^\s*item\s+1a[.\s:–—-]+risk\s+factors\b",
    "Item 7 — Management's Discussion and Analysis": (
        r"(?im)^\s*item\s+7[.\s:–—-]+(?:management.?s\s+discussion|md&a)"
    ),
    "Item 8 — Financial Statements and Supplementary Data": (
        r"(?im)^\s*item\s+8[.\s:–—-]+financial\s+statements"
    ),
    "Part I, Item 1 — Financial Statements": (
        r"(?im)^\s*(?:part\s+i[.\s:–—-]+)?item\s+1[.\s:–—-]+financial\s+statements"
    ),
    "Part I, Item 2 — Management's Discussion and Analysis": (
        r"(?im)^\s*(?:part\s+i[.\s:–—-]+)?item\s+2[.\s:–—-]+management.?s\s+discussion"
    ),
    "Part II, Item 1A — Risk Factors": (
        r"(?im)^\s*part\s+ii[.\s:–—-]+item\s+1a[.\s:–—-]+risk\s+factors"
    ),
}


def extract_sections(text: str, min_section_chars: int = 200) -> dict[str, str]:
    """Extract likely content headings, preferring the last repeated TOC match."""
    if not text.strip():
        return {}
    matches: list[tuple[int, str]] = []
    for name, pattern in SECTION_PATTERNS.items():
        found = list(re.finditer(pattern, text))
        if found:
            # TOCs usually appear first; the final occurrence more often starts content.
            matches.append((found[-1].start(), name))
    matches.sort()
    sections: dict[str, str] = {}
    for index, (start, name) in enumerate(matches):
        end = matches[index + 1][0] if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if len(content) >= min_section_chars:
            sections[name] = content
    if not sections:
        sections["Full Filing (section fallback)"] = text
    return sections
