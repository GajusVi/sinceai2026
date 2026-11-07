"""Builder health view data (steward/estate_view.py, T3.2): the estate grouped by root cause, on the real data pack."""

import time
from datetime import date

import pytest

from steward import estate_view as ev
from steward.catalog import Catalog
from steward.config import ROOT_DIR
from steward.datapack import DEFAULT_XLSX, load_catalog
from steward.decision import lifecycle
from steward.models import ArtifactStatus

AS_OF = date(2026, 11, 7)


@pytest.fixture(scope="module")
def catalog(tmp_path_factory) -> Catalog:
    return load_catalog(DEFAULT_XLSX, ROOT_DIR / "catalog" / "bayer", tmp_path_factory.mktemp("data"), AS_OF)


@pytest.fixture(scope="module")
def view(catalog) -> ev.EstateView:
    return ev.estate_view(catalog)


def test_the_audit_numbers_are_reproduced(view):
    """69 reports on failed refresh sit on 14 models; 65 reports have an inactive owner, held by 13 people; 21 have none."""
    assert (view.total, view.failed_refresh_assets, view.failing_models) == (360, 69, 14)
    assert (view.inactive_owner_assets, view.inactive_owners, view.no_owner_assets) == (65, 13, 21)
    assert len(view.certified_on_failed_refresh) == 16  # a certificate on a report whose data does not refresh


def test_every_problem_report_is_in_exactly_one_group(view, catalog):
    failed = [a.id for a in catalog.active_artifacts() if a.refresh_status == "failed" and a.model_id]
    grouped = [i for f in view.model_fixes for i in f.assets]
    assert sorted(grouped) == sorted(failed) and len(grouped) == len(set(grouped))
    unowned = [a.id for a in catalog.active_artifacts() if a.owner_status != "active"]
    by_owner = [i for f in view.owner_fixes for i in f.assets]
    assert sorted(by_owner) == sorted(unowned) and len(by_owner) == len(set(by_owner))


def test_owner_tiers_match_the_lifecycle_estate_counts(view, catalog):
    tiers = {}
    for f in view.owner_fixes:
        tiers[f.tier] = tiers.get(f.tier, 0) + len(f.assets)
    est = lifecycle.estate(catalog, AS_OF).tiers
    assert tiers == {"a": est["a"], "b": est["b"], "c": est["c"], "none": est["no_owner"]}
    top = next(f for f in view.owner_fixes if f.owner_id)  # the biggest real person
    assert top.name and top.role and (top.tier != "a" or top.successor)


def test_actions_are_ranked_by_reports_healed_and_say_what_to_do(view):
    sizes = [len(a.heals) for a in view.actions]
    assert sizes == sorted(sizes, reverse=True) and len(view.actions) == view.failing_models + len(view.owner_fixes)
    assert {a.kind for a in view.actions} == {"FIX_REFRESH", "REASSIGN_OWNER"}
    fix = next(a for a in view.actions if a.kind == "FIX_REFRESH")
    assert fix.target in fix.text and "reports work again" in fix.text
    assert all(a.text for a in view.actions)


def test_provisional_assets_are_not_part_of_the_estate(catalog):
    base = ev.estate_view(catalog)
    ghost = next(a for a in catalog.active_artifacts() if a.refresh_status == "failed").model_copy(
        update={"id": "AST-GHOST", "status": ArtifactStatus.PROVISIONAL, "expires_at": date(2026, 12, 1)}
    )
    padded = Catalog([*catalog.artifacts.values(), ghost], list(catalog.metrics.values()), list(catalog.dimensions.values()))
    after = ev.estate_view(padded)
    assert after.total == base.total and after.failed_refresh_assets == base.failed_refresh_assets


def test_it_is_a_single_cheap_pass(catalog):
    t = time.time()
    ev.estate_view(catalog)
    assert time.time() - t < 3  # 0.35 s here; the duplicate scan, not this, is what is slow on the large pack


def test_my_assets_lists_one_persons_reports_worst_first(view, catalog):
    est = lifecycle.estate(catalog, AS_OF)
    owner = next(f for f in view.owner_fixes if f.owner_id).owner_id
    mine = ev.my_assets(catalog, owner, frozenset(est.retire))
    assert mine.total == len(next(f for f in view.owner_fixes if f.owner_id == owner).assets)
    assert mine.needing_attention <= mine.total and all(a.id for a in mine.assets)
    assert all("NO_ACTIVE_OWNER" in a.issues for a in mine.assets)  # this owner is inactive
    severity = {"FAILED_REFRESH": 0, "NO_ACTIVE_OWNER": 1, "RETIRE_CANDIDATE": 2, "REFRESH_WARNING": 3, "LOW_USAGE": 4}
    firsts = [min(severity[i] for i in a.issues) for a in mine.assets if a.issues]
    assert firsts == sorted(firsts)
    assert {a.trend for a in mine.assets} <= {"up", "down", "flat", "n/a"}
    assert ev.my_assets(catalog, "OWN-NOBODY").total == 0
