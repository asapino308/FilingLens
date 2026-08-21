from __future__ import annotations

import pytest

from filinglens.documents.chunking import chunk_sections
from filinglens.documents.parser import clean_filing_html
from filinglens.documents.sections import extract_sections


def metadata():
    return {
        "company": "Example Corp",
        "ticker": "EXM",
        "filing_form": "10-K",
        "filing_date": "2025-02-01",
        "accession_number": "0000000000-25-000001",
        "source_url": "https://www.sec.gov/Archives/example.htm",
    }


def test_html_parser_removes_active_content_and_duplicates():
    html = "<html><style>secret</style><script>ignore()</script><body><p>Revenue increased.</p><p>Revenue increased.</p><p>Cash flow improved.</p></body></html>"
    text = clean_filing_html(html)
    assert "secret" not in text
    assert "ignore" not in text
    assert text.count("Revenue increased.") == 1


def test_empty_parser_input():
    assert clean_filing_html("") == ""


def test_section_detection_prefers_content_after_toc():
    body = "Management discussed revenue, competition, liquidity, and operations. " * 20
    text = (
        "Item 1. Business\nItem 1A. Risk Factors\nTable of contents\n"
        + "Item 1. Business\n"
        + body
        + "\nItem 1A. Risk Factors\n"
        + ("Competition and cybersecurity may adversely affect results. " * 20)
    )
    sections = extract_sections(text)
    assert "Item 1 — Business" in sections
    assert sections["Item 1 — Business"].count("Management discussed") == 20
    assert "Item 1A — Risk Factors" in sections


def test_section_fallback_preserves_full_text():
    text = "Unusually formatted filing content. " * 20
    sections = extract_sections(text)
    assert sections == {"Full Filing (section fallback)": text}


def test_chunking_preserves_all_metadata():
    sections = {"Item 7": "word " * 1000}
    chunks = chunk_sections(sections, chunk_words=200, overlap_words=25, **metadata())
    assert len(chunks) > 1
    first = chunks[0]
    assert first.company == "Example Corp"
    assert first.ticker == "EXM"
    assert first.section == "Item 7"
    assert first.source_url.startswith("https://www.sec.gov/")
    assert first.chunk_id.endswith("0001")


def test_chunk_overlap_validation():
    with pytest.raises(ValueError):
        chunk_sections({"x": "word " * 100}, chunk_words=50, overlap_words=50, **metadata())


def test_tiny_fragments_are_skipped():
    chunks = chunk_sections({"x": "brief text"}, **metadata())
    assert chunks == []

