from __future__ import annotations

from filinglens.documents.chunking import FilingChunk
from filinglens.documents.retrieval import LocalRetriever


def make_chunk(text: str, index: int) -> FilingChunk:
    return FilingChunk(
        text=text,
        company="Example Corp",
        ticker="EXM",
        filing_form="10-K",
        filing_date="2025-02-01",
        section=f"Section {index}",
        accession_number="0000000000-25-000001",
        source_url="https://www.sec.gov/Archives/example.htm",
        chunk_id=f"chunk-{index}",
    )


def test_relevant_chunk_ranks_first():
    chunks = [
        make_chunk("Revenue increased because product demand and pricing improved.", 1),
        make_chunk("Cybersecurity incidents could disrupt information systems.", 2),
        make_chunk("The company owns several office buildings.", 3),
    ]
    results = LocalRetriever(chunks).search("What factors affected revenue growth?")
    assert results[0].chunk.section == "Section 1"
    assert results[0].score > 0


def test_source_metadata_survives_retrieval():
    chunk = make_chunk("Liquidity depends on operating cash flow and credit facilities.", 1)
    result = LocalRetriever([chunk]).search("liquidity cash flow")[0]
    assert result.chunk.source_url == chunk.source_url
    assert result.chunk.accession_number == chunk.accession_number


def test_empty_query_returns_no_results():
    assert LocalRetriever([make_chunk("Some text", 1)]).search("   ") == []


def test_empty_corpus_returns_no_results():
    assert LocalRetriever([]).search("revenue") == []


def test_unmatched_query_returns_no_results():
    assert LocalRetriever([make_chunk("Revenue and cash flow", 1)]).search("penguins") == []


def test_top_k_is_respected():
    chunks = [make_chunk(f"Revenue discussion number {i}", i) for i in range(5)]
    assert len(LocalRetriever(chunks).search("revenue", top_k=2)) == 2

