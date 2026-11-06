from __future__ import annotations

from ..catalog import Catalog
from ..linking import artifact_metric_ids
from ..models import ParsedQuestion


def rank_by_structure(question: ParsedQuestion, catalog: Catalog) -> list[str]:
    """Ranks artifacts by how many of the question's metrics and dimensions they share.
    Metrics weigh double: a report with the right metric and wrong slice is closer than the reverse."""
    wanted_dimensions = set(question.dimensions) | set(question.filters)
    scores = {}
    for artifact in catalog.active_artifacts():
        metrics = artifact_metric_ids(artifact.metrics, catalog)
        dimensions = set(artifact.dimensions) | set(artifact.filters)
        score = 2 * len(metrics & set(question.metrics)) + len(dimensions & wanted_dimensions)
        if score:
            scores[artifact.id] = score
    return sorted(scores, key=scores.get, reverse=True)
