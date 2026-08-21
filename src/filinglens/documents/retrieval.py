"""Transparent, deterministic TF-IDF filing retrieval."""

from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .chunking import FilingChunk


@dataclass(frozen=True)
class SearchResult:
    chunk: FilingChunk
    score: float


class LocalRetriever:
    def __init__(self, chunks: list[FilingChunk]) -> None:
        self.chunks = chunks
        self.vectorizer: TfidfVectorizer | None = None
        self.matrix = None
        if chunks:
            self.vectorizer = TfidfVectorizer(
                stop_words="english", ngram_range=(1, 2), min_df=1, sublinear_tf=True
            )
            self.matrix = self.vectorizer.fit_transform(chunk.text for chunk in chunks)

    @staticmethod
    def clean_query(query: str) -> str:
        return re.sub(r"\s+", " ", query).strip()

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        cleaned = self.clean_query(query)
        if not cleaned or not self.chunks or self.vectorizer is None or self.matrix is None:
            return []
        query_vector = self.vectorizer.transform([cleaned])
        scores = (self.matrix @ query_vector.T).toarray().ravel()
        ranked = np.argsort(scores)[::-1]
        return [
            SearchResult(self.chunks[index], float(scores[index]))
            for index in ranked[: max(top_k, 0)]
            if scores[index] > 0
        ]

