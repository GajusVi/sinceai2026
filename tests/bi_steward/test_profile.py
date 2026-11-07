"""semantic.profile / check_visual: what the data shape allows a layout to pick (thresholds: steward/config.py LAYOUT_*)."""

import pytest

from steward import semantic
from steward.config import LAYOUT_MIN_TREND_MONTHS, LAYOUT_RANK_MAX_MEMBERS, LAYOUT_RANK_MIN_MEMBERS


@pytest.fixture(scope="module")
def frames():
    return semantic.load_frames()


@pytest.fixture(scope="module")
def nubeqa(frames):
    return semantic.profile(semantic.all_measures(), frames, {"product": "Nubeqa"})


def test_every_measure_is_profiled_and_gaps_are_only_gaps(nubeqa):
    assert len(nubeqa) == 18
    gaps = [p for p in nubeqa.values() if not p.feasible]
    assert {p.kpi_id for p in gaps} == {"KPI-023", "KPI-034", "KPI-037", "KPI-039", "KPI-046", "KPI-049"}
    assert all(p.forms == ["gap"] and p.gap_reason and p.months == 0 and not p.members for p in gaps)


def test_monthly_kpi_may_trend_and_rank_by_market(nubeqa):
    p = nubeqa["Net Sales"]
    assert p.grain == "month" and p.months >= LAYOUT_MIN_TREND_MONTHS
    assert p.forms == ["card", "line", "bar", "table"]
    assert "market" in p.bar_dimensions and "region" in p.bar_dimensions
    assert "product" not in p.bar_dimensions  # one product in scope: nothing to rank


def test_snapshot_kpi_has_no_trend(nubeqa):
    for name in ("Demand Forecast Accuracy", "Reimbursement Status Coverage", "Certified Asset Share"):
        assert "line" not in nubeqa[name].forms, name


def test_asset_level_kpi_has_no_breakdown(nubeqa):
    p = nubeqa["Report Adoption"]
    assert p.members == {} and p.bar_dimensions == [] and "bar" not in p.forms
    assert "line" in p.forms  # usage is monthly


def test_scope_narrows_what_is_legal(frames):
    one_market = semantic.profile([semantic.measure("KPI-001")], frames, {"market": "FR"})["Net Sales"]
    assert one_market.members["market"] == 1 and "market" not in one_market.bar_dimensions
    assert "bar" in one_market.forms  # still rankable by product (7 products)
    assert one_market.bar_dimensions == ["product"]


def test_rank_thresholds_are_the_config_ones(frames):
    p = semantic.profile([semantic.measure("KPI-001")], frames, {})["Net Sales"]
    for dim, n in p.members.items():
        assert (dim in p.bar_dimensions) == (LAYOUT_RANK_MIN_MEMBERS <= n <= LAYOUT_RANK_MAX_MEMBERS)


def test_data_quality_note_is_carried(frames):
    p = semantic.profile([semantic.measure("KPI-016")], frames, {})["Inventory Coverage"]
    assert any("trap 14" in note for note in p.dq)


def test_check_visual_accepts_legal_and_names_each_problem(nubeqa):
    assert semantic.check_visual(nubeqa, "line", ["Net Sales"], None) == []
    assert semantic.check_visual(nubeqa, "bar", ["Net Sales"], "market") == []
    assert semantic.check_visual(nubeqa, "gap", ["Gross-to-Net Rate"], None) == []
    assert "gap" in semantic.check_visual(nubeqa, "line", ["Gross-to-Net Rate"], None)[0]
    assert "gap card" in semantic.check_visual(nubeqa, "card", ["Budget Variance"], None)[0]
    assert "has data" in semantic.check_visual(nubeqa, "gap", ["Net Sales"], None)[0]
    assert "not legal" in semantic.check_visual(nubeqa, "line", ["Certified Asset Share"], None)[0]
    assert "cannot be ranked" in semantic.check_visual(nubeqa, "bar", ["Net Sales"], "product")[0]
    assert "unknown measure" in semantic.check_visual(nubeqa, "card", ["Batch Yield"], None)[0]
