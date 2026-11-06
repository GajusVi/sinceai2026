"""Links free text to the official dictionary: metric ids, dimension ids and dimension values."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .catalog import Catalog
from .models import ArtifactMetric


@dataclass(frozen=True)
class TermMatch:
    start: int
    end: int
    kind: str  # "metric" | "dimension" | "value"
    id: str
    dimension: str | None = None


def find_terms(text: str, catalog: Catalog) -> list[TermMatch]:
    """Synonyms are word-start stems ("revenu" matches "revenue", "revenues").
    Longer matches win, so "gross revenue" links to gross revenue, not to net revenue via "revenue"."""
    lowered = text.lower()
    found: list[TermMatch] = []

    def scan(synonyms: list[str], kind: str, term_id: str, dimension: str | None = None) -> None:
        for synonym in synonyms:
            for match in re.finditer(rf"(?<!\w){re.escape(synonym.lower())}", lowered):
                found.append(TermMatch(match.start(), match.end(), kind, term_id, dimension))

    for metric in catalog.metrics.values():
        scan(metric.synonyms, "metric", metric.id)
    for dimension in catalog.dimensions.values():
        scan(dimension.synonyms, "dimension", dimension.id)
        for value in dimension.values:
            scan(value.synonyms, "value", value.id, dimension.id)

    found.sort(key=lambda m: (-(m.end - m.start), m.start))
    taken: list[TermMatch] = []
    for match in found:
        if all(match.end <= t.start or match.start >= t.end for t in taken):
            taken.append(match)
    return sorted(taken, key=lambda m: m.start)


def normalize_formula(formula: str) -> str:
    return re.sub(r"\s+", "", formula.lower())


def metric_by_formula(formula: str, catalog: Catalog) -> str | None:
    normalized = normalize_formula(formula)
    for metric in catalog.metrics.values():
        if normalize_formula(metric.formula) == normalized:
            return metric.id
    return None


def metric_by_label(label: str, catalog: Catalog) -> str | None:
    for match in find_terms(label, catalog):
        if match.kind == "metric":
            return match.id
    return None


def resolve_artifact_metric(metric: ArtifactMetric, catalog: Catalog) -> tuple[str | None, str | None]:
    """Returns (claimed, actual): what the label says the metric is, and what its formula really computes."""
    return metric_by_label(metric.label, catalog), metric_by_formula(metric.formula, catalog)


def artifact_metric_ids(metrics: list[ArtifactMetric], catalog: Catalog) -> set[str]:
    """A metric counts as present only when its formula matches the official definition."""
    ids = set()
    for metric in metrics:
        _, actual = resolve_artifact_metric(metric, catalog)
        if actual:
            ids.add(actual)
    return ids
