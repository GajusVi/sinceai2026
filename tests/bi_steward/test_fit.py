"""DECISION T1.2 engine half (Margiris): every carrier is a candidate (F2), C1 metric share for EXTEND, C2 health before
choice, RULE-001 by containment, and the provisional state of T1.6 (asks 1107-194304 / 1107-194721 from Donatas)."""

import json
from pathlib import Path

import pytest
from test_kpi_matching import AS_OF, Pack

from steward.decision import decide, fit
from steward.decision.consolidate import duplicate_clusters
from steward.decision.engine import score_candidates
from steward.decision.lifecycle import estate
from steward.decision.signals import trust
from steward.lint import lint
from steward.models import ArtifactStatus, ParsedQuestion, Verdict
from steward.query_parser import RuleBasedParser
from steward.spec import DashboardSpec

FIXTURE = Path(__file__).parent / "fixtures" / "spec_req0001.json"
PROBES = Path(__file__).resolve().parents[2] / "data" / "holdout" / "probes.jsonl"


@pytest.fixture(scope="module")
def pack():
    return Pack()


def ask(pack, text):
    q = RuleBasedParser(pack.catalog).parse(text)
    return q, decide(q, pack.search.search(q), pack.catalog, AS_OF)


def test_the_decision_does_not_depend_on_text_search_recall(pack):
    """F2: every asset that carries a requested KPI is a candidate. With NO text hits, the answer is unchanged."""
    q = RuleBasedParser(pack.catalog).parse("Xarelto net sales in Germany")
    with_search = decide(q, pack.search.search(q), pack.catalog, AS_OF)
    without = decide(q, [], pack.catalog, AS_OF)
    assert without.verdict == with_search.verdict == Verdict.REUSE
    assert without.best.artifact.id == with_search.best.artifact.id == "AST-0191"


def test_the_retiring_attractor_is_never_the_answer(pack):
    """C2 + done-when of T1.2: AST-0335 (owner inactive, RETIRE) answered 6 of 9 requests once the scan was complete."""
    assert not fit.healthy(pack.catalog.artifact("AST-0335"), pack.catalog, AS_OF)
    for text in (
        "Nubeqa net sales by market",
        "Kerendia net sales in EMEA by month",
        "Please build a new report for market access coverage and reimbursement status by product.",
        "We need one executive view combining net sales, forecast accuracy and inventory coverage for Bayer Pharma.",
    ):
        _, d = ask(pack, text)
        assert d.best is None or d.best.artifact.id != "AST-0335", text


def test_no_chosen_asset_is_retiring_or_failing_on_a_probe_sample(pack):
    """Done-when of T1.2 on every 10th of Martynas's frozen probes (the full 980 run is in the eval)."""
    rows = [json.loads(x) for x in PROBES.read_text(encoding="utf-8").splitlines() if x.strip()][::10]
    for r in rows:
        _, d = ask(pack, r["text"])
        if d.best:
            assert fit.healthy(d.best.artifact, pack.catalog, AS_OF), (r["id"], d.best.artifact.id)


def test_extend_needs_half_of_the_requested_kpis(pack):
    """C1: REQ-0001 asks for 3 KPIs; the closest healthy report carries 1, so CREATE (filters no longer count)."""
    q, d = ask(
        pack, "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country."
    )
    assert d.verdict == Verdict.CREATE and "50%" in d.reasons[0]
    q2, d2 = ask(pack, "Nubeqa net sales growth and forecast variance globally by country.")
    assert d2.verdict == Verdict.EXTEND and fit.metric_share(d2.best, q2) >= 0.5


def test_a_reusable_report_wins_over_a_higher_scored_one_that_is_not(pack):
    """Martynas B1: the verdict is about the best REUSE-eligible candidate when one exists."""
    q, d = ask(pack, "Xarelto net sales in Germany")
    assert d.verdict == Verdict.REUSE
    others = score_candidates(q, pack.search.search(q), pack.catalog, AS_OF)
    assert all(
        not (
            c.compatible
            and c.coverage == 1.0
            and c.score > d.best.score
            and fit.healthy(c.artifact, pack.catalog, AS_OF)
            and c.trust >= 0.6
            and c.artifact.platform != "Tableau"
        )
        for c in others
        if c.artifact.id != d.best.artifact.id
    )


def test_reuse_of_an_unendorsed_report_attaches_certify(pack):
    _, d = ask(pack, "Xarelto net sales in Germany")
    assert d.verdict == Verdict.REUSE and d.best.artifact.endorsement == "none"
    assert any("certified" in e.claim and d.best.artifact.id in e.record_ids for e in d.evidence)


def test_rule_001_blocks_a_create_when_one_report_already_carries_every_kpi(pack):
    """Containment, not Jaccard: one requested KPI inside a three-KPI report is a reuse
    (it used to say 'a new dashboard is justified')."""
    spec = DashboardSpec.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    spec.change_type, spec.base_asset_ids, spec.measures = "create", [], []
    spec.kpi_ids, spec.filters = ["KPI-001"], {"product": "Xarelto", "market": "DE"}
    r001 = next(r for r in lint(spec, pack.catalog, AS_OF) if r.rule_id == "RULE-001")
    assert r001.status == "block" and "AST-0191" in r001.record_ids


def test_rule_001_ignores_a_retiring_substitute(pack):
    spec = DashboardSpec.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    spec.change_type, spec.base_asset_ids, spec.measures, spec.filters = "create", [], [], {}
    attractor = pack.catalog.artifact("AST-0335")
    spec.kpi_ids = sorted(attractor.kpi_ids)[:1]
    r001 = next(r for r in lint(spec, pack.catalog, AS_OF) if r.rule_id == "RULE-001")
    assert "AST-0335" not in r001.record_ids


# -- provisional (T1.6, Donatas's asks) ---------------------------------------------------------------------------


def provisional(asset, **update):
    return asset.model_copy(
        update={
            "id": f"{asset.family_id}-v9",
            "version": 9,
            "status": ArtifactStatus.PROVISIONAL,
            "views_30d": 0,
            "endorsement": "none",
            **update,
        }
    )


def test_a_provisional_asset_has_no_trust_until_used_or_certified(pack):
    base = pack.catalog.artifact("AST-0191")
    assert trust(provisional(base), AS_OF) == 0.0
    assert trust(provisional(base, views_30d=5), AS_OF) > 0.0
    assert trust(provisional(base, endorsement="certified"), AS_OF) > 0.0


def test_provisional_assets_are_outside_the_retire_funnel(pack):
    base = pack.catalog.artifact("AST-0335")
    copy = provisional(base)
    before = estate(pack.catalog, AS_OF)
    pack.catalog.artifacts[copy.id] = copy
    try:
        after = estate(pack.catalog, AS_OF)
    finally:
        del pack.catalog.artifacts[copy.id]
    assert copy.id not in after.retire and after.funnel["assets"] == before.funnel["assets"]


def test_an_approved_version_is_not_a_duplicate_of_its_own_base(pack):
    base = pack.catalog.artifact("AST-0015")
    copy = provisional(base, views_30d=3)
    q = ParsedQuestion(text="x", metrics=["net_sales_growth"], filters={"product": "P-NUB", "market": "Global"})
    pool = [c for c in score_candidates(q, [], pack.catalog, AS_OF)]
    from steward.search import SearchHit

    candidates = score_candidates(q, [SearchHit(base, 1.0, {}), SearchHit(copy, 0.9, {})], pack.catalog, AS_OF)
    assert pool == [] and not any(
        {base.id, copy.id} <= {m.artifact.id for m in cl.members} for cl in duplicate_clusters(candidates, pack.catalog)
    )
