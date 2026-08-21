"""Run the same grounded prompts against selectable local models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from filinglens.documents.retrieval import LocalRetriever
from filinglens.llm.grounded_qa import ask_filing
from filinglens.llm.base import LLMProvider

from .qa_eval import EvaluationQuestion, citation_present, reports_insufficient_evidence


@dataclass(frozen=True)
class BenchmarkRecord:
    model_id: str
    question: str
    category: str
    answer: str
    citation_present: bool
    insufficient_evidence: bool
    latency_seconds: float | None
    output_length: int


def run_benchmark(
    provider: LLMProvider,
    retriever: LocalRetriever,
    models: Iterable[str],
    questions: Iterable[EvaluationQuestion],
    verified_metrics: str = "",
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for model in models:
        for question in questions:
            result = ask_filing(
                question.question,
                retriever,
                provider,
                verified_metrics=verified_metrics,
                model=model,
            )
            record = BenchmarkRecord(
                model_id=model,
                question=question.question,
                category=question.category,
                answer=result.answer,
                citation_present=citation_present(result.answer),
                insufficient_evidence=reports_insufficient_evidence(result.answer),
                latency_seconds=(result.generation.latency_seconds if result.generation else None),
                output_length=len(result.answer),
            )
            records.append(asdict(record))
    return records

