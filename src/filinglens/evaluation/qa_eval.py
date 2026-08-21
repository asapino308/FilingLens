"""Reusable filing-Q&A evaluation dataset and simple compliance checks."""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class EvaluationQuestion:
    question: str
    category: str
    expected_terms: tuple[str, ...] = ()
    deliberately_unsupported: bool = False


EVALUATION_QUESTIONS = (
    EvaluationQuestion("What does the company identify as its principal business?", "direct retrieval"),
    EvaluationQuestion("What factors did management say affected revenue?", "MD&A reasoning"),
    EvaluationQuestion("What factors affected operating margin?", "financial-change explanation"),
    EvaluationQuestion("How does management describe liquidity?", "MD&A reasoning"),
    EvaluationQuestion("What were the major business risks?", "risk synthesis"),
    EvaluationQuestion("What changed in capital expenditures?", "financial-change explanation"),
    EvaluationQuestion("How does management describe competitive pressure?", "risk synthesis"),
    EvaluationQuestion("What changed in debt levels?", "financial-change explanation"),
    EvaluationQuestion("What affected operating cash flow?", "financial-change explanation"),
    EvaluationQuestion("What does management say about inflation?", "risk synthesis"),
    EvaluationQuestion("Which operating segments are discussed?", "direct retrieval"),
    EvaluationQuestion("What legal or regulatory risks are described?", "risk synthesis"),
    EvaluationQuestion("What geographic risks are discussed?", "risk synthesis"),
    EvaluationQuestion("How did revenue growth compare with the verified metric?", "metric grounding"),
    EvaluationQuestion("How did operating margin compare with the verified metric?", "metric grounding"),
    EvaluationQuestion("What does the filing say about dividends or repurchases?", "direct retrieval"),
    EvaluationQuestion("What supply-chain risks are described?", "risk synthesis"),
    EvaluationQuestion("What cybersecurity risks are discussed?", "risk synthesis"),
    EvaluationQuestion(
        "What will the company's stock price be exactly one year from today?",
        "unsupported",
        deliberately_unsupported=True,
    ),
    EvaluationQuestion(
        "What private conversation did the CEO have with the board yesterday?",
        "unsupported",
        deliberately_unsupported=True,
    ),
)


def citation_present(answer: str) -> bool:
    return bool(re.search(r"\[Source\s+\d+\]", answer, flags=re.IGNORECASE))


def reports_insufficient_evidence(answer: str) -> bool:
    lowered = answer.lower()
    return any(term in lowered for term in ("insufficient", "not provide enough", "cannot determine"))

