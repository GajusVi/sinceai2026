from __future__ import annotations

import math
from collections import Counter
from typing import Protocol

from ..llm import GeminiClient
from .text import tokenize


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[dict[str, float]] | list[list[float]]: ...


class HashingEmbedder:
    """Offline stand-in for real embeddings: character trigrams of stemmed tokens.
    Catches spelling variants, not meaning. Swap for GeminiEmbedder when a key is available."""

    def embed(self, texts: list[str]) -> list[dict[str, float]]:
        vectors = []
        for text in texts:
            grams: Counter[str] = Counter()
            for token in tokenize(text):
                padded = f"#{token}#"
                grams.update(padded[i : i + 3] for i in range(len(padded) - 2))
            vectors.append(dict(grams))
        return vectors


class GeminiEmbedder:
    def __init__(self, llm: GeminiClient):
        self.llm = llm

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.llm.embed(texts)


def cosine(a, b) -> float:
    if isinstance(a, dict):
        dot = sum(v * b.get(k, 0.0) for k, v in a.items())
        norm_a = math.sqrt(sum(v * v for v in a.values()))
        norm_b = math.sqrt(sum(v * v for v in b.values()))
    else:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


class SemanticIndex:
    def __init__(self, documents: dict[str, str], embedder: Embedder):
        self.embedder = embedder
        self.ids = list(documents)
        self.vectors = embedder.embed([documents[i] for i in self.ids]) if self.ids else []

    def rank(self, query: str, min_similarity: float = 0.05) -> list[str]:
        query_vector = self.embedder.embed([query])[0]
        scored = [(doc_id, cosine(query_vector, vector)) for doc_id, vector in zip(self.ids, self.vectors)]
        return [doc_id for doc_id, score in sorted(scored, key=lambda x: x[1], reverse=True) if score >= min_similarity]
