"""Grounded filing Q&A combining retrieved evidence and verified Python metrics."""

from __future__ import annotations

from dataclasses import dataclass
import re

from filinglens.documents.retrieval import LocalRetriever, SearchResult

from .base import GenerationResult, LLMProvider
from .prompts import GROUNDING_SYSTEM_PROMPT


@dataclass(frozen=True)
class GroundedAnswer:
    answer: str
    sources: tuple[SearchResult, ...]
    generation: GenerationResult | None
    status: str = "answered"


_FILING_TERMS = {
    "acquisition",
    "asset",
    "balance",
    "board",
    "business",
    "capital",
    "cash",
    "company",
    "competition",
    "cost",
    "customer",
    "debt",
    "director",
    "dividend",
    "employee",
    "expense",
    "financial",
    "firm",
    "growth",
    "income",
    "liability",
    "liquidity",
    "management",
    "margin",
    "operation",
    "product",
    "profit",
    "regulation",
    "revenue",
    "risk",
    "sale",
    "segment",
    "service",
    "share",
    "stock",
    "strategy",
    "supplier",
    "tax",
}

_CLEARLY_UNSUPPORTED_PATTERNS = (
    r"\bweather\b",
    r"\bsuper\s+bowl\b",
    r"\bsports?\s+(?:score|result|winner)\b",
    r"\b(?:recipe|restaurant|movie|song|travel)\b",
    r"\bshould\s+i\s+(?:buy|sell|trade)\b",
    r"\bis\s+.{0,40}\s+a\s+(?:buy|sell)\b",
    r"\b(?:buy|sell)\s+recommendation\b",
    r"\b(?:price|stock)\s+target\b",
    r"\b(?:stock|share)\s+price\s+(?:tomorrow|next\s+week|next\s+month)\b",
    r"\bwhat\s+will\s+.{0,60}\b(?:stock|share)\s+price\b",
    r"\b(?:predict|forecast|estimate)\b.{0,60}\b(?:stock|share)\s+price\b",
)


def _tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    expanded = set(tokens)
    for token in tokens:
        if token.endswith("ies") and len(token) > 4:
            expanded.add(f"{token[:-3]}y")
        elif token.endswith("s") and len(token) > 3:
            expanded.add(token[:-1])
    return expanded


def question_is_in_scope(question: str, results: list[SearchResult]) -> bool:
    """Conservatively reject only questions clearly unrelated to filing evidence."""
    cleaned = LocalRetriever.clean_query(question)
    if not cleaned or not results:
        return False
    if any(
        re.search(pattern, cleaned, flags=re.IGNORECASE)
        for pattern in _CLEARLY_UNSUPPORTED_PATTERNS
    ):
        return False

    question_tokens = _tokens(cleaned)
    if question_tokens & _FILING_TERMS:
        return True

    # Exact lexical overlap avoids false positives such as "weather" matching
    # the common filing word "whether" in TF-IDF retrieval.
    evidence_tokens = _tokens(" ".join(result.chunk.text for result in results))
    meaningful = {token for token in question_tokens if len(token) >= 4}
    return bool(meaningful & evidence_tokens)


def _evidence_text(results: list[SearchResult]) -> str:
    blocks = []
    for index, result in enumerate(results, 1):
        chunk = result.chunk
        blocks.append(
            f"[Source {index}]\nForm: {chunk.filing_form}\nFiled: {chunk.filing_date}\n"
            f"Section: {chunk.section}\nAccession: {chunk.accession_number}\n"
            f"URL: {chunk.source_url}\nEvidence: {chunk.text}"
        )
    return "\n\n".join(blocks)


def ask_filing(
    question: str,
    retriever: LocalRetriever,
    provider: LLMProvider,
    *,
    verified_metrics: str = "No verified metrics were supplied for this question.",
    model: str | None = None,
    top_k: int = 4,
) -> GroundedAnswer:
    results = retriever.search(question, top_k=top_k)
    if not question_is_in_scope(question, results):
        return GroundedAnswer(
            "This question appears to be outside the indexed filing's scope or lacks relevant "
            "filing evidence. Ask about the company's business, financial performance, liquidity, "
            "management discussion, or risk factors. FilingLens does not provide price predictions "
            "or buy/sell recommendations.",
            (),
            None,
            status="out_of_scope",
        )
    user_prompt = f"""Question: {question}

Verified FilingLens metrics (calculated in Python):
{verified_metrics}

Retrieved filing evidence:
{_evidence_text(results)}

Answer the question concisely, cite filing-derived statements with [Source N], and state when the evidence is insufficient.
"""
    generation = provider.generate(
        [
            {"role": "system", "content": GROUNDING_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        max_tokens=900,
        reasoning="off",
    )
    return GroundedAnswer(generation.text, tuple(results), generation)
