"""Transparent, deterministic TF-IDF filing retrieval without a heavy ML runtime."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re

from .chunking import FilingChunk


# Common function words add noise to filing searches. Keep this list deliberately
# small so financial and business terms remain searchable.
_STOP_WORDS = frozenset(
    "a an and are as at be been by can could did do does for from had has have "
    "he her hers him his how i if in into is it its may more most my no not of "
    "on or our ours she should so some such than that the their theirs them "
    "there these they this those to was we were what when where which who why "
    "will with would you your yours".split()
)
_TOKEN = re.compile(r"(?u)\b\w\w+\b")


def _terms(text: str) -> Counter[str]:
    words = [word for word in _TOKEN.findall(text.lower()) if word not in _STOP_WORDS]
    return Counter(words + [f"{left} {right}" for left, right in zip(words, words[1:])])


def _normalize(weights: dict[str, float]) -> dict[str, float]:
    length = math.sqrt(sum(weight * weight for weight in weights.values()))
    return {term: weight / length for term, weight in weights.items()} if length else {}


@dataclass(frozen=True)
class SearchResult:
    chunk: FilingChunk
    score: float


class LocalRetriever:
    def __init__(self, chunks: list[FilingChunk]) -> None:
        self.chunks = chunks
        counts = [_terms(chunk.text) for chunk in chunks]
        document_frequency = Counter(term for terms in counts for term in terms)
        self.idf = {
            term: math.log((1 + len(chunks)) / (1 + frequency)) + 1
            for term, frequency in document_frequency.items()
        }
        self.vectors = [
            _normalize({term: (1 + math.log(count)) * self.idf[term]
                        for term, count in terms.items()})
            for terms in counts
        ]

    @staticmethod
    def clean_query(query: str) -> str:
        return re.sub(r"\s+", " ", query).strip()

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        cleaned = self.clean_query(query)
        if not cleaned or not self.chunks or top_k <= 0:
            return []
        query_counts = _terms(cleaned)
        query_vector = _normalize({
            term: (1 + math.log(count)) * self.idf[term]
            for term, count in query_counts.items() if term in self.idf
        })
        if not query_vector:
            return []
        scores = [sum(weight * vector.get(term, 0.0)
                      for term, weight in query_vector.items()) for vector in self.vectors]
        ranked = sorted(range(len(scores)), key=lambda index: (-scores[index], index))
        return [SearchResult(self.chunks[index], scores[index])
                for index in ranked[:top_k] if scores[index] > 0]
