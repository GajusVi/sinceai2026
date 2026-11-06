"""Catalog health: duplicates, stale and ownerless reports, and candidates to retire."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from itertools import combinations

from pydantic import BaseModel

from .catalog import Catalog
from .config import DUPLICATE_THRESHOLD, LOW_USAGE_VIEWS, STALE_AFTER_DAYS
from .decision.minhash import MinHashCalculator
from .decision.signals import trust
from .linking import artifact_covered_metrics
from .models import Artifact


class DuplicatePair(BaseModel):
    keep_id: str
    duplicate_id: str
    similarity: float


class RetireCandidate(BaseModel):
    artifact_id: str
    title: str
    reasons: list[str]


class CatalogHealth(BaseModel):
    total: int
    certified: int
    duplicates: list[DuplicatePair]
    stale: list[str]
    no_owner: list[str]
    retire: list[RetireCandidate]


def _features(artifact: Artifact, catalog: Catalog) -> tuple[frozenset[str], frozenset[str]]:
    metrics = frozenset(artifact_covered_metrics(artifact, catalog))
    return metrics, metrics | frozenset(artifact.dimensions) | frozenset(artifact.filters)


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def catalog_health(catalog: Catalog, as_of: date) -> CatalogHealth:
    artifacts = catalog.active_artifacts()
    minhash = MinHashCalculator(shingle_size=3)
    signatures = {a.id: minhash.compute_signature(a.description) for a in artifacts}

    # Features once per asset, and only assets with the same non-empty metric set can be duplicates.
    features = {a.id: _features(a, catalog) for a in artifacts}
    by_metrics: dict[frozenset[str], list[Artifact]] = defaultdict(list)
    for a in artifacts:
        if features[a.id][0]:
            by_metrics[features[a.id][0]].append(a)

    duplicates = []
    for group in by_metrics.values():
        for a, b in combinations(group, 2):
            if a.family_id == b.family_id:
                continue
            similarity = max(
                _jaccard(features[a.id][1], features[b.id][1]), minhash.estimate_jaccard(signatures[a.id], signatures[b.id])
            )
            if similarity < DUPLICATE_THRESHOLD:
                continue
            keep, duplicate = sorted([a, b], key=lambda x: (trust(x, as_of), x.views_30d), reverse=True)
            duplicates.append(DuplicatePair(keep_id=keep.id, duplicate_id=duplicate.id, similarity=round(similarity, 2)))

    # A copy of a copy should point to the original, not to the other copy.
    duplicate_ids = {p.duplicate_id for p in duplicates}
    duplicates = [p for p in duplicates if p.keep_id not in duplicate_ids]

    stale = [a.id for a in artifacts if (as_of - a.last_refreshed).days > STALE_AFTER_DAYS]
    no_owner = [a.id for a in artifacts if not a.has_owner]

    reasons: dict[str, list[str]] = {}
    for pair in duplicates:
        reasons.setdefault(pair.duplicate_id, []).append(
            f"duplicate of \"{catalog.artifact(pair.keep_id).title}\" ({pair.similarity:.0%} similar)"
        )
    for a in artifacts:
        if a.id in stale and a.views_30d < LOW_USAGE_VIEWS:
            reasons.setdefault(a.id, []).append(f"not refreshed for {(as_of - a.last_refreshed).days} days and barely used")
        if not a.has_owner and a.id in reasons:
            reasons[a.id].append("no active owner")

    retire = [
        RetireCandidate(artifact_id=artifact_id, title=catalog.artifact(artifact_id).title, reasons=r)
        for artifact_id, r in reasons.items()
    ]
    return CatalogHealth(
        total=len(artifacts),
        certified=sum(a.certified for a in artifacts),
        duplicates=duplicates,
        stale=stale,
        no_owner=no_owner,
        retire=retire,
    )
