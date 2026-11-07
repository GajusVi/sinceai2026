"""Duplicate clusters among a question's candidates (N6). Real pairs from the data pack, wrapped as Candidates."""

from itertools import combinations

import pytest
from test_kpi_matching import AS_OF, Pack

from steward.decision.consolidate import cluster_evidence, duplicate_clusters
from steward.decision.engine import _with_duplicates, decide
from steward.linking import asset_metric_ids, kpi_jaccard
from steward.models import Candidate, Decision, ParsedQuestion, Verdict

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture(scope="module")
def catalog():
    return Pack().catalog


def candidate(asset, trust, compatible=True, covered=("metric:x",)):
    return Candidate(
        artifact=asset,
        search_score=1.0,
        coverage=1.0,
        trust=trust,
        covered=list(covered),
        gaps=[],
        compatible=compatible,
        score=trust,
    )


@pytest.fixture(scope="module")
def duplicate_pair(catalog):
    arts = catalog.active_artifacts()
    metrics = {a.id: asset_metric_ids(a, catalog) for a in arts}
    return next(
        (a, b)
        for a, b in combinations(arts, 2)
        if a.product_scope == b.product_scope and kpi_jaccard(metrics[a.id], metrics[b.id]) >= 0.6
    )


def test_data_pack_has_the_documented_46_same_product_pairs(catalog):
    """docs/challenge/03_DATA_PACK.md trap 7: 46 same-product asset pairs share >= 60% of canonical metrics."""
    arts = catalog.active_artifacts()
    metrics = {a.id: asset_metric_ids(a, catalog) for a in arts}
    pairs = [
        (a, b)
        for a, b in combinations(arts, 2)
        if a.product_scope == b.product_scope and kpi_jaccard(metrics[a.id], metrics[b.id]) >= 0.6
    ]
    assert len(pairs) == 46


def test_pair_becomes_a_cluster_keeper_is_the_most_trusted(catalog, duplicate_pair):
    a, b = duplicate_pair
    clusters = duplicate_clusters([candidate(a, 0.4), candidate(b, 0.8)], catalog)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.keeper.artifact.id == b.id and [c.artifact.id for c in cluster.others] == [a.id]
    assert cluster.overlap[a.id] >= 0.6


def test_evidence_cites_rule_001_and_both_record_ids(catalog, duplicate_pair):
    a, b = duplicate_pair
    cluster = duplicate_clusters([candidate(a, 0.4), candidate(b, 0.8)], catalog)[0]
    (evidence,) = cluster_evidence(cluster)
    assert evidence.rule_id == "RULE-001" and evidence.record_ids == [a.id, b.id] and a.id in evidence.claim


def test_incompatible_or_uncovered_candidates_are_not_clustered(catalog, duplicate_pair):
    a, b = duplicate_pair
    assert duplicate_clusters([candidate(a, 0.4), candidate(b, 0.8, compatible=False)], catalog) == []
    assert duplicate_clusters([candidate(a, 0.4), candidate(b, 0.8, covered=("filter:product",))], catalog) == []


def test_different_product_scope_is_not_a_duplicate(catalog):
    arts = catalog.active_artifacts()
    metrics = {a.id: asset_metric_ids(a, catalog) for a in arts}
    a, b = next(
        (a, b)
        for a, b in combinations(arts, 2)
        if a.product_scope != b.product_scope and metrics[a.id] and metrics[a.id] == metrics[b.id]
    )
    assert duplicate_clusters([candidate(a, 0.4), candidate(b, 0.8)], catalog) == []


# Verdict precedence, option A (Gajus, 1107-034521): the best asset answers; CONSOLIDATE only if no member is REUSE-eligible.
def test_planted_duplicates_become_a_consolidate_verdict_with_the_most_trusted_keeper():
    pack = Pack()
    a, b = pack.catalog.artifact("AST-0064"), pack.catalog.artifact("AST-0338")
    metrics = sorted(asset_metric_ids(a, pack.catalog) & asset_metric_ids(b, pack.catalog))
    narrower = b if len(b.filters) >= len(a.filters) else a
    question = ParsedQuestion(text="x", metrics=metrics, filters=dict(narrower.filters))
    decision = decide(question, pack.search.search(question), pack.catalog, AS_OF)
    assert decision.verdict == Verdict.CONSOLIDATE and decision.flags == ["CONSOLIDATE"]
    assert decision.best.artifact.id in {a.id, b.id}
    other = ({a.id, b.id} - {decision.best.artifact.id}).pop()
    assert other in {c.artifact.id for c in decision.alternatives}
    claims = [e for e in decision.evidence if e.rule_id == "RULE-001"]
    assert claims and set(claims[0].record_ids) == {a.id, b.id}
    assert decision.best.trust >= max(c.trust for c in decision.alternatives if c.artifact.id == other)


def test_a_reuse_eligible_member_keeps_the_verdict_and_the_duplicates_ride_along(catalog, duplicate_pair):
    a, b = duplicate_pair
    best = candidate(b, 0.9)
    best.coverage = 1.0
    best.artifact = best.artifact.model_copy(update={"platform": "Power BI"})
    reuse = Decision(verdict=Verdict.REUSE, best=best)
    out = _with_duplicates(reuse, [best, candidate(a, 0.4)], catalog)
    assert out.verdict == Verdict.REUSE and out.flags == ["CONSOLIDATE"]
    assert any(e.rule_id == "RULE-001" and a.id in e.record_ids for e in out.evidence)


def test_no_cluster_no_change(catalog, duplicate_pair):
    _, b = duplicate_pair
    best = candidate(b, 0.9)
    best.coverage = 1.0
    reuse = Decision(verdict=Verdict.REUSE, best=best)
    assert _with_duplicates(reuse, [best], catalog) == reuse
