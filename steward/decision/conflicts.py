from __future__ import annotations

from ..catalog import Catalog
from ..linking import normalize_formula, resolve_artifact_metric
from ..models import MetricConflict


def find_conflicts(metric_ids: list[str], catalog: Catalog) -> list[MetricConflict]:
    """Reports whose metric is named like an official metric but computed differently.
    Example: "Revenue" in a dashboard that is really gross revenue, while official revenue is net."""
    wanted = set(metric_ids)
    conflicts = []
    for artifact in catalog.active_artifacts():
        for metric in artifact.metrics:
            claimed, actual = resolve_artifact_metric(metric, catalog)
            if claimed not in wanted:
                continue
            official = catalog.metric(claimed)
            if normalize_formula(metric.formula) == normalize_formula(official.formula):
                continue
            conflicts.append(
                MetricConflict(
                    artifact_id=artifact.id,
                    artifact_title=artifact.title,
                    label=metric.label,
                    metric_id=claimed,
                    artifact_formula=metric.formula,
                    official_formula=official.formula,
                    actual_metric_id=actual,
                )
            )
    return conflicts
