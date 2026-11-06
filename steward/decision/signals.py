from __future__ import annotations

from datetime import date

from ..catalog import Catalog
from ..linking import artifact_metric_ids
from ..models import Artifact, Gap, GapKind, ParsedQuestion

# A coarser time grain the question asks for can be built from these finer ones.
TIME_ROLLUP = {
    "quarter": {"quarter", "month"},
    "month": {"month"},
    "week": {"week"},
}


def required_items(question: ParsedQuestion) -> list[Gap]:
    """Everything a report must support to answer the question. Each item is one unit of coverage."""
    items = [Gap(kind=GapKind.METRIC, key=m) for m in question.metrics]
    items += [Gap(kind=GapKind.FILTER, key=d, value=v) for d, v in question.filters.items()]
    items += [Gap(kind=GapKind.DIMENSION, key=d) for d in question.dimensions]
    return items


def coverage(question: ParsedQuestion, artifact: Artifact, catalog: Catalog) -> tuple[float, list[str], list[Gap], bool]:
    """Returns (coverage share, covered item keys, gaps, compatible).

    An artifact is incompatible when it is locked to a different scope than asked:
    a report fixed to EMEA cannot be extended to answer a LATAM question."""
    metrics = artifact_metric_ids(artifact.metrics, catalog)
    dimensions = set(artifact.dimensions)
    covered: list[str] = []
    gaps: list[Gap] = []
    compatible = True

    items = required_items(question)
    for item in items:
        if item.kind == GapKind.METRIC:
            ok = item.key in metrics
        elif item.kind == GapKind.FILTER:
            fixed = artifact.filters.get(item.key)
            if fixed is not None and fixed != item.value:
                compatible = False
                gaps.append(Gap(kind=GapKind.SCOPE, key=item.key, value=fixed))
                continue
            ok = fixed == item.value or item.key in dimensions
        else:
            ok = bool(TIME_ROLLUP.get(item.key, {item.key}) & dimensions)

        if ok:
            covered.append(f"{item.kind.value}:{item.key}")
        else:
            gaps.append(item)

    for dimension_id, value_id in artifact.filters.items():
        if dimension_id not in question.filters:
            compatible = False
            gaps.append(Gap(kind=GapKind.SCOPE, key=dimension_id, value=value_id))

    share = len(covered) / len(items) if items else 0.0
    return round(share, 2), covered, gaps, compatible


def trust(artifact: Artifact, as_of: date) -> float:
    score = 0.0
    if artifact.certified:
        score += 0.4
    if artifact.has_owner:
        score += 0.2
    age = (as_of - artifact.last_refreshed).days
    if age <= 7:
        score += 0.25
    elif age <= 30:
        score += 0.15
    elif age <= 90:
        score += 0.05
    if artifact.views_30d >= 50:
        score += 0.15
    elif artifact.views_30d >= 10:
        score += 0.05
    return round(score, 2)


def trust_gaps(artifact: Artifact, as_of: date) -> list[Gap]:
    gaps = []
    if not artifact.certified:
        gaps.append(Gap(kind=GapKind.TRUST, key="certification"))
    if not artifact.has_owner:
        gaps.append(Gap(kind=GapKind.TRUST, key="owner"))
    if (as_of - artifact.last_refreshed).days > 30:
        gaps.append(Gap(kind=GapKind.TRUST, key="freshness"))
    return gaps
