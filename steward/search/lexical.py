from __future__ import annotations

import math
from collections import Counter

from .text import tokenize


class BM25Index:
    def __init__(self, documents: dict[str, str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.docs = {doc_id: Counter(tokenize(text)) for doc_id, text in documents.items()}
        self.lengths = {doc_id: sum(tokens.values()) for doc_id, tokens in self.docs.items()}
        self.avg_length = sum(self.lengths.values()) / max(len(self.docs), 1)
        document_frequency: Counter[str] = Counter()
        for tokens in self.docs.values():
            document_frequency.update(tokens.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in document_frequency.items()}

    def rank(self, query: str) -> list[str]:
        terms = set(tokenize(query))
        scores = {}
        for doc_id, tokens in self.docs.items():
            score = 0.0
            for term in terms:
                tf = tokens.get(term, 0)
                if not tf:
                    continue
                norm = self.k1 * (1 - self.b + self.b * self.lengths[doc_id] / self.avg_length)
                score += self.idf[term] * tf * (self.k1 + 1) / (tf + norm)
            if score > 0:
                scores[doc_id] = score
        return sorted(scores, key=scores.get, reverse=True)
