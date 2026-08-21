"""Section-aware word-window chunking with complete source metadata."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re


@dataclass(frozen=True)
class FilingChunk:
    text: str
    company: str
    ticker: str
    filing_form: str
    filing_date: str
    section: str
    accession_number: str
    source_url: str
    chunk_id: str


def chunk_sections(
    sections: dict[str, str],
    *,
    company: str,
    ticker: str,
    filing_form: str,
    filing_date: str,
    accession_number: str,
    source_url: str,
    chunk_words: int = 450,
    overlap_words: int = 60,
) -> list[FilingChunk]:
    if chunk_words <= overlap_words or overlap_words < 0:
        raise ValueError("chunk_words must be greater than a non-negative overlap_words")
    chunks: list[FilingChunk] = []
    seen: set[str] = set()
    step = chunk_words - overlap_words
    for section, text in sections.items():
        words = re.findall(r"\S+", text)
        for start in range(0, len(words), step):
            window = " ".join(words[start : start + chunk_words]).strip()
            if len(window) < 120:
                continue
            fingerprint = hashlib.sha1(window.encode("utf-8")).hexdigest()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            chunks.append(
                FilingChunk(
                    text=window,
                    company=company,
                    ticker=ticker.upper(),
                    filing_form=filing_form,
                    filing_date=filing_date,
                    section=section,
                    accession_number=accession_number,
                    source_url=source_url,
                    chunk_id=f"{accession_number}-{len(chunks) + 1:04d}",
                )
            )
            if start + chunk_words >= len(words):
                break
    return chunks

