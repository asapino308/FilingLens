"""Source-grounded analyst brief generation."""

from __future__ import annotations

from filinglens.documents.retrieval import LocalRetriever

from .base import GenerationResult, LLMProvider
from .grounded_qa import _evidence_text
from .prompts import ANALYST_BRIEF_SECTIONS, GROUNDING_SYSTEM_PROMPT


def generate_analyst_brief(
    ticker: str,
    verified_metrics: str,
    anomaly_summary: str,
    retriever: LocalRetriever,
    provider: LLMProvider,
    *,
    model: str | None = None,
) -> GenerationResult:
    query = "business overview revenue margin liquidity debt cash flow major risk factors management discussion"
    evidence = retriever.search(query, top_k=4)
    sections = "\n".join(f"## {section}" for section in ANALYST_BRIEF_SECTIONS)
    prompt = f"""Prepare an educational analyst brief for {ticker} using exactly these headings:
{sections}

Verified FilingLens metrics (Python calculations):
{verified_metrics}

Unusual-change screen (not fraud detection):
{anomaly_summary}

Retrieved filing evidence:
{_evidence_text(evidence)}

Use [Source N] citations for filing-derived claims. Do not create unsupported claims. End with: Educational financial-analysis software. Not investment advice.
"""
    return provider.generate(
        [
            {"role": "system", "content": GROUNDING_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        model=model,
        max_tokens=1400,
        reasoning="off",
    )
