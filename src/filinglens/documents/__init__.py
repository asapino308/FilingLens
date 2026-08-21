"""Filing parsing, sectioning, chunking, and local retrieval."""

from .chunking import FilingChunk, chunk_sections
from .parser import clean_filing_html
from .retrieval import LocalRetriever, SearchResult
from .sections import extract_sections

__all__ = [
    "FilingChunk",
    "LocalRetriever",
    "SearchResult",
    "chunk_sections",
    "clean_filing_html",
    "extract_sections",
]

