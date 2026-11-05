"""Small-corpus retrieval for citations/RAG. Local embeddings (fastembed, ONNX, CPU) with a
TF-IDF fallback that always works offline. Hackathon corpora fit in memory: no vector DB."""

from dataclasses import dataclass, field

import numpy as np

from .config import ROOT, get_settings

MODEL_DIR = ROOT / "models"


def _embedder():
    try:
        from fastembed import TextEmbedding

        return TextEmbedding(get_settings().embed_model, cache_dir=str(MODEL_DIR))
    except Exception:
        return None


@dataclass
class Index:
    texts: list[str] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)
    _vecs: np.ndarray | None = None
    _tfidf = None
    backend: str = ""

    def build(self, texts: list[str], ids: list[str] | None = None) -> "Index":
        self.texts, self.ids = texts, ids or [str(i) for i in range(len(texts))]
        emb = _embedder()
        if emb is not None:
            v = np.array(list(emb.embed(texts)), dtype=np.float32)
            self.backend = "fastembed"
            self._emb = emb
        else:
            from sklearn.feature_extraction.text import TfidfVectorizer

            self._tfidf = TfidfVectorizer(ngram_range=(1, 2), min_df=1, token_pattern=r"(?u)\b\w+\b").fit(texts)
            v = self._tfidf.transform(texts).toarray().astype(np.float32)
            self.backend = "tfidf"
        self._vecs = v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)
        return self

    def search(self, query: str, k: int = 5) -> list[tuple[str, float, str]]:
        if self.backend == "fastembed":
            q = np.array(list(self._emb.embed([query])), dtype=np.float32)[0]
        else:
            q = self._tfidf.transform([query]).toarray().astype(np.float32)[0]
        q = q / (np.linalg.norm(q) + 1e-9)
        scores = self._vecs @ q
        top = np.argsort(-scores)[:k]
        return [(self.ids[i], float(scores[i]), self.texts[i]) for i in top]
