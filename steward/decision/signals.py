from __future__ import annotations

from datetime import date

from ..catalog import Catalog
from ..linking import artifact_covered_metrics
from ..models import Artifact, ArtifactStatus, Gap, GapKind, ParsedQuestion

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
    metrics = artifact_covered_metrics(artifact, catalog)
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


def trust_datapack(artifact: Artifact) -> float:
    """BUILD_PLAN 2.3 on real fields: endorsement, accountable owner, model refresh, reach, minus open high signals.
    Platform is not part of trust (it only blocks REUSE for Tableau).
    A provisional asset (approved here, DECISION C4) has no trust until it is used or certified."""
    if artifact.status == ArtifactStatus.PROVISIONAL and artifact.views_30d <= 0 and artifact.endorsement == "none":
        return 0.0
    score = {"certified": 0.40, "promoted": 0.25}.get(artifact.endorsement, 0.0)
    if artifact.owner_status == "active":
        score += 0.20
    elif artifact.owner_status == "inactive" and artifact.successor_candidates:
        score += 0.10  # owner left but the role is still staffed
    score += {"healthy": 0.25, "warning": 0.10}.get(artifact.refresh_status, 0.0)
    if artifact.usage:
        avg_users = sum(u.unique_users for u in artifact.usage) / len(artifact.usage)
        score += 0.15 if avg_users >= 50 else 0.05 if avg_users >= 10 else 0.0
    open_high = sum(1 for sig in artifact.signals if sig.split(":")[1:3] == ["high", "open"])
    return round(max(score - 0.10 * open_high, 0.0), 2)


def trust(artifact: Artifact, as_of: date) -> float:
    if artifact.platform:  # data-pack asset
        return trust_datapack(artifact)
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
    if artifact.platform:
        if artifact.endorsement != "certified":
            gaps.append(Gap(kind=GapKind.TRUST, key="certification"))
        if artifact.owner_status != "active":
            gaps.append(Gap(kind=GapKind.TRUST, key="owner"))
        if artifact.refresh_status != "healthy":
            gaps.append(Gap(kind=GapKind.TRUST, key="refresh"))
        return gaps
    if not artifact.certified:
        gaps.append(Gap(kind=GapKind.TRUST, key="certification"))
    if not artifact.has_owner:
        gaps.append(Gap(kind=GapKind.TRUST, key="owner"))
    if (as_of - artifact.last_refreshed).days > 30:
        gaps.append(Gap(kind=GapKind.TRUST, key="freshness"))
    return gaps
