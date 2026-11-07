""" "Does it already exist?" (DECISION T1.2): the shared checks behind the verdict, lint RULE-001 and the worker path.

- `coverage_index`: canonical metric id -> ids of the active assets that carry it (the decision reads every asset that
  carries a requested KPI, not only the top-40 text hits: Gajus F2).
- `retire_ids`: the assets BUILD_PLAN 2.2 recommends retiring, computed once per catalog and as-of date.
- `healthy`: C2 (Gajus, 19:35). A report on the RETIRE list or on a failed refresh is never the answer: it cannot be
  reused and it is not chosen as the base of an extension. An inactive owner or a missing endorsement does not block;
  they become attached actions (REASSIGN_OWNER, certify).
- `metric_share`: C1. An EXTEND needs at least half of the requested KPIs; filters and breakdowns do not count.
- `same_family_provisional`: an approved version (status provisional) and its own base are one asset, not duplicates.

Data-pack assets only. The sample catalog has no KPI ids, no RETIRE list and no refresh status, so it is untouched.
"""

from __future__ import annotations

from datetime import date

from ..catalog import Catalog
from ..linking import artifact_covered_metrics
from ..models import Artifact, ArtifactStatus, Candidate, GapKind, ParsedQuestion

EXTEND_MIN_METRIC_SHARE = 0.5  # C1


def coverage_index(catalog: Catalog) -> dict[str, set[str]]:
    cached = getattr(catalog, "_coverage_index", None)
    if cached is None:
        cached = {}
        for a in catalog.active_artifacts():
            for metric_id in artifact_covered_metrics(a, catalog):
                cached.setdefault(metric_id, set()).add(a.id)
        catalog._coverage_index = cached
    return cached


def carriers(question: ParsedQuestion, catalog: Catalog) -> set[str]:
    """Every active asset that carries at least one requested metric."""
    index = coverage_index(catalog)
    return set().union(*(index.get(m, set()) for m in question.metrics)) if question.metrics else set()


def retire_ids(catalog: Catalog, as_of: date) -> set[str]:
    cache = getattr(catalog, "_retire_ids", None)
    if cache is None:
        cache = catalog._retire_ids = {}
    if as_of not in cache:
        from .lifecycle import estate  # lazy: reads the Owners/KPI sheets of the data pack

        cache[as_of] = set(estate(catalog, as_of).retire)
    return cache[as_of]


def is_provisional(artifact: Artifact) -> bool:
    return artifact.status == ArtifactStatus.PROVISIONAL


def health_problems(artifact: Artifact, catalog: Catalog, as_of: date | None) -> list[str]:
    """Why this report must not be the answer (empty = healthy). Data-pack assets only. No as_of: refresh only."""
    if not artifact.platform:
        return []
    problems = []
    if artifact.refresh_status == "failed":
        problems.append("failed refresh")
    if as_of is not None and artifact.id in retire_ids(catalog, as_of):
        problems.append("recommended for retirement")
    return problems


def healthy(artifact: Artifact, catalog: Catalog, as_of: date | None) -> bool:
    return not health_problems(artifact, catalog, as_of)


def metric_share(candidate: Candidate, question: ParsedQuestion) -> float:
    if not question.metrics:
        return 0.0
    covered = {c.split(":", 1)[1] for c in candidate.covered if c.startswith(f"{GapKind.METRIC.value}:")}
    return len(covered & set(question.metrics)) / len(question.metrics)


def same_family_provisional(a: Artifact, b: Artifact) -> bool:
    return a.family_id == b.family_id and (is_provisional(a) or is_provisional(b))
