from __future__ import annotations

from dataclasses import dataclass

from ..catalog import Catalog
from ..linking import artifact_covered_metrics
from ..models import Artifact, ParsedQuestion
from .lexical import BM25Index
from .rrf import reciprocal_rank_fusion
from .semantic import Embedder, HashingEmbedder, SemanticIndex
from .structural import rank_by_structure


@dataclass
class SearchHit:
    artifact: Artifact
    score: float
    ranks: dict[str, int | None]


class CatalogSearch:
    def __init__(self, catalog: Catalog, embedder: Embedder | None = None):
        self.catalog = catalog
        documents = {a.id: self._document(a) for a in catalog.active_artifacts()}
        self.lexical = BM25Index(documents)
        self.semantic = SemanticIndex(documents, embedder or HashingEmbedder())

    def search(self, question: ParsedQuestion, limit: int = 40) -> list[SearchHit]:
        query = self._query(question)
        rankings = {
            "lexical": self.lexical.rank(query),
            "semantic": self.semantic.rank(query),
            "structural": rank_by_structure(question, self.catalog),
        }
        fused = reciprocal_rank_fusion(list(rankings.values()))
        hits = []
        for artifact_id, score in fused[:limit]:
            ranks = {name: (r.index(artifact_id) + 1 if artifact_id in r else None) for name, r in rankings.items()}
            hits.append(SearchHit(self.catalog.artifact(artifact_id), score, ranks))
        return hits

    def _document(self, artifact: Artifact) -> str:
        """Catalog entries are in English and questions are often in Russian, so both sides
        are expanded with dictionary names of the linked metrics and dimensions."""
        metric_names = [self.catalog.metric(m).name for m in artifact_covered_metrics(artifact, self.catalog)]
        dimension_names = [self.catalog.dimension(d).name for d in artifact.dimensions if d in self.catalog.dimensions]
        filter_labels = [self.catalog.dimension_value_label(d, v) for d, v in artifact.filters.items()]
        return " ".join(
            [artifact.title, artifact.description, artifact.domain]
            + [m.label for m in artifact.metrics]
            + metric_names
            + dimension_names
            + list(artifact.filters.values())
            + filter_labels
        )

    def _query(self, question: ParsedQuestion) -> str:
        parts = [question.text]
        parts += [self.catalog.metric(m).name for m in question.metrics]
        parts += [self.catalog.dimension(d).name for d in question.dimensions]
        for dimension_id, value_id in question.filters.items():
            parts += [value_id, self.catalog.dimension_value_label(dimension_id, value_id)]
        return " ".join(parts)
