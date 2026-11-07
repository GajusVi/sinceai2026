"""Links free text to the official dictionary: metric ids, dimension ids and dimension values."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .catalog import Catalog
from .config import AMBIGUOUS_PHRASES
from .models import Artifact, ArtifactMetric


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

    blocked = [m.span() for phrase in AMBIGUOUS_PHRASES for m in re.finditer(rf"(?<!\w){re.escape(phrase)}", lowered)]
    found = [f for f in found if not any(f.start < end and start < f.end for start, end in blocked)]
    found.sort(key=lambda m: (-(m.end - m.start), m.start))
    taken: list[TermMatch] = []
    for match in found:
        if all(match.end <= t.start or match.start >= t.end for t in taken):
            taken.append(match)
    return sorted(taken, key=lambda m: m.start)


GLOBAL_SCOPE = "Global"
_GLOBAL = re.compile(r"(?<!\w)(?:global(?:ly)?|worldwide)(?!\w)")


def asks_global(text: str) -> bool:
    """"global" in a request is a scope filter (market=Global), not a breakdown. BUILD_PLAN 2.4, decision of 2026-11-07."""
    return bool(_GLOBAL.search(text.lower()))


def apply_global_scope(filters: dict[str, str], text: str, catalog: Catalog) -> None:
    """Adds market=Global when the text says "global" and no market was named. Only on catalogs that have a market dimension."""
    if "market" in catalog.dimensions and "market" not in filters and "region" not in filters and asks_global(text):
        filters["market"] = GLOBAL_SCOPE


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


def kpi_index(catalog: Catalog) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """From MetricDefinition.kpi_id/variants: (canonical kpi_id -> metric id, variant kpi_id -> (metric id, definition_status)).
    Empty for the sample catalog. Cached on the catalog object, which is rebuilt on reload."""
    cached = getattr(catalog, "_kpi_index", None)
    if cached is None:
        canonical = {m.kpi_id: m.id for m in catalog.metrics.values() if m.kpi_id}
        variants = {v.kpi_id: (m.id, v.definition_status) for m in catalog.metrics.values() for v in m.variants}
        cached = catalog._kpi_index = (canonical, variants)
    return cached


def artifact_covered_metrics(artifact: Artifact, catalog: Catalog) -> set[str]:
    """Data-pack assets: a metric is present only if the asset carries its canonical KPI id (variants never count).
    Sample catalog (no kpi_ids): the formula must match the official definition."""
    if not artifact.kpi_ids:
        return artifact_metric_ids(artifact.metrics, catalog)
    canonical, _ = kpi_index(catalog)
    return {canonical[k] for k in artifact.kpi_ids if k in canonical}


def artifact_variants(artifact: Artifact, catalog: Catalog) -> list[tuple[str, str, str]]:
    """(variant kpi_id, canonical metric id, definition_status) for each non-canonical KPI the asset uses."""
    _, variants = kpi_index(catalog)
    return [(k, *variants[k]) for k in artifact.kpi_ids if k in variants]
