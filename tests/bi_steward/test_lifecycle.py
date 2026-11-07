"""Lifecycle flags (BUILD_PLAN 11.2): FIX_REFRESH, REASSIGN_OWNER (3 tiers), RETIRE / HUMAN_REVIEW, MIGRATE evidence.
Real data-pack assets for the tiers; a synthetic copy of a real asset where the data pack has no example."""

from datetime import date

import pytest

from steward.decision.lifecycle import (
    assess_retire,
    bottom_cuts,
    fix_refresh,
    kpi_holders,
    migrate_evidence,
    reassign_owner,
    reference,
    retire_evidence,
)
from steward.models import UsageMonth

AS_OF = date(2026, 11, 7)


@pytest.fixture(scope="module")
def catalog():
    import tempfile
    from pathlib import Path

    from steward.config import ROOT_DIR
    from steward.datapack import DEFAULT_XLSX, load_catalog

    return load_catalog(DEFAULT_XLSX, ROOT_DIR / "catalog" / "bayer", Path(tempfile.mkdtemp()))


@pytest.fixture(scope="module")
def ref():
    return reference()


def test_fix_refresh_cites_model_and_asset(catalog):
    a = catalog.artifact("AST-0001")
    (ev,) = fix_refresh(a)
    assert ev.rule_id == "RULE-005" and a.model_id in ev.record_ids and a.id in ev.record_ids


def test_healthy_model_has_no_fix_refresh(catalog):
    healthy = next(a for a in catalog.active_artifacts() if a.refresh_status == "healthy")
    assert fix_refresh(healthy) == []


def test_reassign_tier_a_same_role_same_scope(catalog, ref):
    a = catalog.artifact("AST-0011")
    (ev,) = reassign_owner(a, ref)
    assert "Proposed successor: OWN-009" in ev.claim and "OWN-009" in ev.record_ids


def test_reassign_tier_b_lists_other_scope_candidates(catalog, ref):
    a = catalog.artifact("AST-0025")
    (ev,) = reassign_owner(a, ref)
    assert "steward picks" in ev.claim and "OWN-021" in ev.record_ids


def test_reassign_tier_c_vacant_role_goes_to_platform_owner(catalog, ref):
    a = catalog.artifact("AST-0009")
    (ev,) = reassign_owner(a, ref)
    assert "vacant" in ev.claim and "BI Platform Owner" in ev.claim and "OWN-026" in ev.record_ids


def test_active_owner_has_no_reassign(catalog, ref):
    a = next(a for a in catalog.active_artifacts() if a.owner_status == "active")
    assert reassign_owner(a, ref) == []


def test_reassign_tiers_match_the_data_pack_doc(catalog, ref):
    """03_DATA_PACK: 65 inactive owners split 23 same scope / 21 other scope / 21 vacant, plus 21 with no owner."""
    inactive = [a for a in catalog.active_artifacts() if a.owner_status == "inactive"]
    missing = [a for a in catalog.active_artifacts() if a.owner_status not in ("active", "inactive")]
    claims = [reassign_owner(a, ref)[0].claim for a in inactive]
    assert len(inactive) == 65 and len(missing) == 21
    assert sum("Proposed successor" in c for c in claims) == 23
    assert sum("steward picks" in c for c in claims) == 21
    assert sum("vacant" in c for c in claims) == 21
    assert all("BI Platform Owner" in reassign_owner(a, ref)[0].claim for a in missing)


def test_funnel_gives_21_retire_candidates_and_none_leaves_a_critical_kpi_bare(catalog, ref):
    """Option B (Gajus 11:41): every other condition holds for 21 assets; retiring all of them still leaves every
    high-criticality KPI with at least one active report."""
    cuts, holders = bottom_cuts(catalog), kpi_holders(catalog)
    results = [assess_retire(a, catalog, AS_OF, ref, cuts, holders) for a in catalog.active_artifacts()]
    retire = {r.artifact_id for r in results if r.retire}
    assert len(retire) == 21 and not any(r.human_review for r in results)
    for kpi in ref.high_kpis & set(holders):
        assert holders[kpi] - retire, f"{kpi} would have no report left"


def test_sole_holder_of_a_critical_kpi_goes_to_human_review_not_retire(catalog, ref):
    a = catalog.artifact("AST-0009")
    holders = {k: {a.id} for k in a.kpi_ids}  # pretend no other report carries its KPIs
    r = assess_retire(a, catalog, AS_OF, ref, holders=holders)
    assert r.human_review and not r.retire and r.critical_kpis
    (ev,) = retire_evidence(a, r, catalog, AS_OF)
    assert "only report carrying" in ev.claim and "not recommended for retirement" in ev.claim and a.id in ev.record_ids


def test_critical_kpi_carried_by_another_report_does_not_block_retire(catalog, ref):
    a = catalog.artifact("AST-0009")
    r = assess_retire(a, catalog, AS_OF, ref)
    assert r.retire and not r.critical_kpis
    claims = " ".join(e.claim for e in retire_evidence(a, r, catalog, AS_OF))
    assert "retire candidate" in claims and "Never automatic" in claims and "no active owner" in claims


def _retire_candidate(catalog, ref):
    return catalog.artifact("AST-0009")


@pytest.mark.parametrize(
    "change, failed",
    [
        ({"created_date": date(2026, 10, 1)}, "old_enough"),
        ({"downstream_ids": ["AST-0001"]}, "quiet"),
        ({"owner_status": "active"}, "reason"),
    ],
)
def test_any_failed_condition_blocks_retire(catalog, ref, change, failed):
    a = _retire_candidate(catalog, ref).model_copy(update=change)
    r = assess_retire(a, catalog, AS_OF, ref)
    assert not r.retire and not r.checks[failed]


def test_a_subscription_or_recent_users_block_retire(catalog, ref):
    base = _retire_candidate(catalog, ref)
    recent = base.usage[-1]
    busy = [*base.usage[:-1], UsageMonth(**{**recent.model_dump(), "unique_users": 50})]
    subscribed = [*base.usage[:-1], UsageMonth(**{**recent.model_dump(), "subscriptions": 2})]
    assert not assess_retire(base.model_copy(update={"usage": busy}), catalog, AS_OF, ref).checks["low_use"]
    assert not assess_retire(base.model_copy(update={"usage": subscribed}), catalog, AS_OF, ref).checks["quiet"]


def test_migrate_evidence_only_for_tableau_and_says_claim(catalog, ref):
    tableau = next(a for a in catalog.active_artifacts() if a.platform == "Tableau" and a.id in ref.backlog)
    claims = " ".join(e.claim for e in migrate_evidence(tableau, ref))
    assert "A claim, not a fact" in claims
    powerbi = next(a for a in catalog.active_artifacts() if a.platform == "Power BI")
    assert migrate_evidence(powerbi, ref) == []


# -- L6: the Catalog health view uses the same rule and its counts match docs/challenge/03_DATA_PACK.md -------------


def test_estate_numbers_match_the_data_pack_doc(catalog):
    from steward.decision.lifecycle import estate

    e = estate(catalog, AS_OF)
    assert e.inactive_owner == 65 and e.no_owner == 21  # 86 assets without an accountable active owner
    assert e.tiers == {"a": 23, "b": 21, "c": 21, "no_owner": 21}
    assert e.certified_on_failed_refresh == 16
    steps = [e.funnel[k] for k in ("assets", "old_enough", "low_use", "quiet", "reason", "not_critical")]
    assert steps == sorted(steps, reverse=True) and steps[0] == 360  # a funnel only narrows
    assert len(e.retire) == steps[-1] == 21 and e.human_review == {}


def test_catalog_health_on_the_data_pack_reports_the_lifecycle_rule(catalog):
    from steward.health import catalog_health

    h = catalog_health(catalog, AS_OF)
    assert len(h.retire) == 21 and h.retire_funnel["assets"] == 360
    assert h.ownership["certified_on_failed_refresh"] == 16
    assert all("Never automatic" in " ".join(c.reasons) for c in h.retire)
