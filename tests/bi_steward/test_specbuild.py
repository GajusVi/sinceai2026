"""N3: verdict -> DashboardSpec for REUSE, EXTEND and CREATE on three real questions of the data pack."""
from dataclasses import replace
from datetime import date

import pytest

from steward import Steward
from steward.config import Settings
from steward.intent import Intent
from steward.models import Verdict
from steward.semantic import feasibility
from steward.specbuild import best_model, build_spec, spec_hash

pytestmark = pytest.mark.filterwarnings("ignore")

REQ1 = "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country."


@pytest.fixture(scope="module")
def steward(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("STEWARD_CATALOG", "datapack")
    data_dir = tmp_path_factory.mktemp("s")
    yield Steward(settings=replace(Settings.from_env(), use_llm="off", data_dir=data_dir, as_of=date(2026, 11, 6)))
    mp.undo()


def spec_for(steward, text):
    result = steward.build(steward.ask(text))
    return result.decision, result.spec


def check_layout(spec):
    visuals = [v for p in spec.pages for v in p.visuals]
    names = {m.name for m in spec.measures}
    assert all(set(v.measures) <= names for v in visuals)
    assert len(spec.pages) <= 2 and len(visuals) <= 7 and sum(v.type == "card" for v in visuals) <= 4
    assert all(c.record_ids for c in spec.changes)  # RULE-008
    assert spec.provenance["layout_source"] == "template" and spec.provenance["spec_hash"] == spec_hash(spec)
    assert "Synthetic" in spec.data_label


def test_reuse_shows_the_asset_unchanged(steward):
    decision, spec = spec_for(steward, "Net sales for Eylea in Japan")
    assert decision.verdict == Verdict.REUSE
    assert spec.change_type == "reuse" and spec.base_asset_ids == [decision.best.artifact.id] and spec.changes == []
    assert spec.version == decision.best.artifact.version and spec.owner_id == decision.best.artifact.owner_id
    assert spec.filters == {"product": "Eylea", "market": "JP"}
    check_layout(spec)


def test_extend_adds_the_missing_measures_and_fixes_the_owner(steward):
    decision, spec = spec_for(steward, REQ1)
    asset = decision.best.artifact
    assert decision.verdict == Verdict.EXTEND and spec.change_type == "extend" and spec.base_asset_ids == [asset.id]
    assert spec.version == asset.version + 1
    added = {c.record_ids[1] for c in spec.changes if c.kind == "add_measure"}
    assert added == {"KPI-004", "KPI-042"} - set(asset.kpi_ids)
    owner_change = [c for c in spec.changes if c.kind == "assign_owner"]
    assert asset.owner_status != "active" and owner_change and owner_change[0].record_ids[0] == asset.id
    assert spec.owner_id in asset.successor_candidates
    types = [v.type for v in spec.pages[0].visuals]
    assert types == ["card"] * 3 + ["line", "bar", "table"]
    table = spec.pages[0].visuals[-1]
    assert table.threshold == 10.0 and table.measures == ["Forecast Variance"]
    check_layout(spec)


def test_create_picks_a_governed_power_bi_model_with_its_owner(steward):
    decision, spec = spec_for(steward, "Net sales and OTIF for Hyrnuo in China")
    assert decision.verdict == Verdict.CREATE and spec.change_type == "create" and spec.base_asset_ids == []
    chosen = best_model(Intent(products=["Hyrnuo"], markets=["CN"]))
    assert chosen["endorsement"] in ("certified", "promoted") and chosen["refresh_status"] == "healthy"
    assert spec.source_model_id == chosen["model_id"] and spec.owner_id == chosen["owner_id"]
    assert [c.kind for c in spec.changes] == ["assign_owner"]
    check_layout(spec)


def test_spec_is_deterministic(steward):
    assert spec_for(steward, REQ1)[1].model_dump_json() == spec_for(steward, REQ1)[1].model_dump_json()


def test_infeasible_kpis_stay_as_gap_measures_with_a_gap_card(steward):
    intent = Intent(products=["All Pharma"], metric_ids=["net_sales", "gross_to_net_rate", "budget_variance"])
    decision = steward.ask("Net sales for Eylea in Japan").decision  # a REUSE decision as the base
    spec = build_spec(decision, intent, steward.catalog, feasibility(intent))
    gaps = [m for m in spec.measures if not m.feasible]
    assert [m.kpi_id for m in gaps] == ["KPI-034", "KPI-039"] and all(m.gap_reason for m in gaps)
    cards = [v for v in spec.pages[0].visuals if v.type == "card"]
    assert {c.measures[0] for c in cards} >= {m.name for m in gaps}
    # a gap is never a trend, a breakdown or an exception table
    gap_names = {g.name for g in gaps}
    assert all(not gap_names & set(v.measures) for v in spec.pages[0].visuals if v.type != "card")


def test_clarify_and_not_feasible_build_nothing(steward):
    decision = steward.ask("Show me something interesting").decision
    assert decision.verdict == Verdict.CLARIFY
    assert build_spec(decision, Intent(), steward.catalog, feasibility(Intent())) is None
    assert steward.build(steward.ask("Show me something interesting")).spec is None


def test_build_returns_the_result_with_the_spec_and_leaves_the_original_alone(steward):
    result = steward.ask(REQ1)
    assert result.spec is None  # ask() does not build
    built = steward.build(result)
    assert built.spec is not None and built.decision == result.decision and result.spec is None
    from steward.models import StewardResult

    assert StewardResult.model_validate_json(built.model_dump_json()).spec == built.spec  # survives the round trip
