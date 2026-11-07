"""Duplicate clusters among the candidates of one question (BUILD_PLAN 2.1 CONSOLIDATE, N6).

A cluster = compatible candidates that cover at least one requested metric, share the product scope and overlap on canonical metrics (variant KPIs count as their metric) with Jaccard >= CONSOLIDATE_JACCARD (connected components). The keeper is the most trusted member; the rest are the
retirement candidates. Where the verdict puts CONSOLIDATE relative to REUSE/EXTEND is decided in engine.py, not here.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..catalog import Catalog
from ..config import CONSOLIDATE_JACCARD
from ..linking import asset_metric_ids, kpi_jaccard
from ..models import Candidate, Evidence


@dataclass
class Cluster:
    keeper: Candidate
    others: list[Candidate]
    overlap: dict[str, float]  # other asset id -> KPI Jaccard with the keeper

    @property
    def members(self) -> list[Candidate]:
        return [self.keeper, *self.others]


def duplicate_clusters(candidates: list[Candidate], catalog: Catalog) -> list[Cluster]:
    """All clusters of >= 2 members, the one holding the best candidate first."""
    pool = [c for c in candidates if c.compatible and any(i.startswith("metric:") for i in c.covered)]
    kpis = {c.artifact.id: asset_metric_ids(c.artifact, catalog) for c in pool}

    def linked(a: Candidate, b: Candidate) -> bool:
        return (
            a.artifact.product_scope == b.artifact.product_scope
            and kpi_jaccard(kpis[a.artifact.id], kpis[b.artifact.id]) >= CONSOLIDATE_JACCARD
        )

    seen: set[str] = set()
    clusters: list[Cluster] = []
    for seed in pool:
        if seed.artifact.id in seen:
            continue
        component, frontier = [seed], [seed]
        seen.add(seed.artifact.id)
        while frontier:
            current = frontier.pop()
            for other in pool:
                if other.artifact.id not in seen and linked(current, other):
                    seen.add(other.artifact.id)
                    component.append(other)
                    frontier.append(other)
        if len(component) >= 2:
            keeper = max(component, key=lambda c: (c.trust, c.score))
            others = [c for c in component if c is not keeper]
            overlap = {
                c.artifact.id: round(kpi_jaccard(kpis[keeper.artifact.id], kpis[c.artifact.id]), 2) for c in others
            }
            clusters.append(Cluster(keeper, others, overlap))
    return clusters  # pool is sorted best first, so the best candidate's cluster comes first


def cluster_evidence(cluster: Cluster) -> list[Evidence]:
    return [
        Evidence(
            claim=f"{c.artifact.id} duplicates {cluster.keeper.artifact.id}: same product scope, {cluster.overlap[c.artifact.id]:.0%} KPI overlap",
            rule_id="RULE-001",
            record_ids=[c.artifact.id, cluster.keeper.artifact.id],
            value=f"trust {c.trust:.2f} vs keeper {cluster.keeper.trust:.2f}",
            severity="warning",
        )
        for c in cluster.others
    ]
