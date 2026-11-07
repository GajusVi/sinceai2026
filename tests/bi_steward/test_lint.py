"""One pass and one fail test per lint rule (BUILD_PLAN 5.2), made by editing copies of the REQ-0001 fixture."""

import json
from pathlib import Path

import pytest
from test_kpi_matching import Pack

from steward.linking import kpi_index
from steward.lint import RULES, can_approve, lint, worst
from steward.spec import DashboardSpec, Measure, Page, SpecChange, Visual

pytestmark = pytest.mark.filterwarnings("ignore")
FIXTURE = Path(__file__).parent / "fixtures" / "spec_req0001.json"


@pytest.fixture(scope="module")
def catalog():
    return Pack().catalog


@pytest.fixture
def spec():
    return DashboardSpec.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def result(spec, catalog, rule):
    return next(r for r in lint(spec, catalog) if r.rule_id == rule)


def avg_users(a):
    return sum(u.unique_users for u in a.usage) / len(a.usage) if a.usage else 0


def test_every_rule_reports_once_in_fixed_order(spec, catalog):
    assert [r.rule_id for r in lint(spec, catalog)] == list(RULES)


def test_fixture_has_no_block_and_one_honest_warning(spec, catalog):
    """The REQ-0001 spec can be approved. RULE-005 warns: model SM-069 has no endorsement and the audience is leadership."""
    results = lint(spec, catalog)
    spec.lint = results
    assert can_approve(spec) and worst(results) == "warn"
    assert [r.rule_id for r in results if r.status == "warn"] == ["RULE-005"]


def test_can_approve_needs_a_lint_run_and_no_block(spec, catalog):
    assert not can_approve(spec)  # never linted
    spec.owner_id = ""
    spec.lint = lint(spec, catalog)
    assert not can_approve(spec)


# RULE-001
def test_rule_001_create_is_blocked_when_a_substitute_exists(spec, catalog):
    canonical = set(kpi_index(catalog)[0])
    asset = next(
        a
        for a in catalog.active_artifacts()
        if a.market_scope == "Global" and a.product_scope == "All Pharma" and len(set(a.kpi_ids) & canonical) >= 2
    )
    spec.change_type, spec.base_asset_ids, spec.filters, spec.measures = "create", [], {}, []
    spec.kpi_ids = sorted(set(asset.kpi_ids) & canonical)
    r = result(spec, catalog, "RULE-001")
    assert r.status == "block" and asset.id in r.record_ids


def test_rule_001_create_passes_on_a_scope_nobody_covers(spec, catalog):
    spec.change_type, spec.base_asset_ids, spec.filters = "create", [], {"product": "Nubeqa", "market": "ZZ"}
    assert result(spec, catalog, "RULE-001").status == "pass"


def test_rule_001_does_not_apply_to_extend(spec, catalog):
    assert "Not applicable" in result(spec, catalog, "RULE-001").message


# RULE-002
def test_rule_002_variant_kpi_blocks_and_names_the_canonical_one(spec, catalog):
    spec.measures[0] = Measure(
        name="Inventory",
        kpi_id="KPI-018",
        expression="AVERAGE(fact_pmm[inventory_weeks_syn])",
        definition_status="duplicate_candidate",
    )
    r = result(spec, catalog, "RULE-002")
    assert r.status == "block" and "KPI-016" in r.message


def test_rule_002_a_written_exception_downgrades_to_warn(spec, catalog):
    spec.measures[0] = Measure(
        name="Inventory", kpi_id="KPI-018", expression="x", definition_status="duplicate_candidate"
    )
    spec.provenance["exception:KPI-018"] = "legacy contract needs the local definition"
    r = result(spec, catalog, "RULE-002")
    assert r.status == "warn" and "legacy contract" in r.message


def test_rule_002_passes_with_canonical_kpis(spec, catalog):
    assert result(spec, catalog, "RULE-002").status == "pass"


# RULE-003
def test_rule_003_missing_owner_blocks(spec, catalog):
    spec.owner_id = ""
    assert result(spec, catalog, "RULE-003").status == "block"


def test_rule_003_inactive_owner_blocks_and_active_passes(spec, catalog):
    spec.owner_id = next(a.owner_id for a in catalog.active_artifacts() if a.owner_status == "inactive")
    assert result(spec, catalog, "RULE-003").status == "block"
    spec.owner_id = "OWN-004"
    assert result(spec, catalog, "RULE-003").status == "pass"


# RULE-004
def test_rule_004_no_source_model_blocks(spec, catalog):
    spec.source_model_id = ""
    assert result(spec, catalog, "RULE-004").status == "block"


def test_rule_004_consolidation_must_list_downstream_impact(spec, catalog):
    keeper = next(a for a in catalog.active_artifacts() if a.platform == "Power BI")
    retire = next(a for a in catalog.active_artifacts() if a.downstream_ids and a.id != keeper.id)
    spec.change_type, spec.base_asset_ids = "consolidate", [keeper.id, retire.id]
    spec.changes = [SpecChange(kind="merge_from", detail="merge", record_ids=[retire.id])]
    r = result(spec, catalog, "RULE-004")
    assert r.status == "block" and set(retire.downstream_ids) <= set(r.record_ids)
    spec.changes = [SpecChange(kind="merge_from", detail="merge", record_ids=[retire.id, *retire.downstream_ids])]
    assert result(spec, catalog, "RULE-004").status == "pass"


# RULE-005
def test_rule_005_failed_refresh_blocks(spec, catalog):
    failed = next(a for a in catalog.active_artifacts() if a.refresh_status == "failed")
    spec.source_model_id = failed.model_id
    assert result(spec, catalog, "RULE-005").status == "block"


def test_rule_005_warning_refresh_warns_and_trusted_healthy_model_passes(spec, catalog):
    warning = next(a for a in catalog.active_artifacts() if a.refresh_status == "warning")
    spec.source_model_id = warning.model_id
    assert result(spec, catalog, "RULE-005").status == "warn"
    good = next(
        a
        for a in catalog.active_artifacts()
        if a.refresh_status == "healthy" and a.model_endorsement in {"certified", "promoted"}
    )
    spec.source_model_id, spec.audience, spec.base_asset_ids = good.model_id, "operations team", []
    assert result(spec, catalog, "RULE-005").status == "pass"


# RULE-006
def test_rule_006_migrating_a_low_use_asset_one_to_one_blocks(spec, catalog):
    low = next(a for a in catalog.active_artifacts() if a.platform == "Tableau" and avg_users(a) < 10)
    spec.change_type, spec.base_asset_ids, spec.filters = "migrate", [low.id], {"market": "ZZ"}
    r = result(spec, catalog, "RULE-006")
    assert r.status == "block" and low.id in r.record_ids


def test_rule_006_clean_migration_passes(spec, catalog):
    good = catalog.artifact("AST-0019")  # Tableau, about 51 users a month
    spec.change_type, spec.base_asset_ids, spec.filters = "migrate", [good.id], {"market": "ZZ"}
    assert result(spec, catalog, "RULE-006").status == "pass"


# RULE-007
def test_rule_007_technical_titles_wrong_axis_and_unbound_measures_warn(spec, catalog):
    spec.pages[0].visuals += [
        Visual(type="bar", title="KPI-001 net_sales", measures=["Net Sales"], dimension="market"),
        Visual(type="line", title="Trend", measures=["Net Sales"], dimension="market"),
        Visual(type="card", title="Ghost", measures=["No Such Measure"]),
    ]
    r = result(spec, catalog, "RULE-007")
    assert (
        r.status == "warn"
        and "technical" in r.message
        and "month axis" in r.message
        and "not a defined measure" in r.message
    )


def test_rule_007_fixture_passes(spec, catalog):
    assert result(spec, catalog, "RULE-007").status == "pass"


# RULE-008
def test_rule_008_change_without_record_ids_blocks(spec, catalog):
    spec.changes.append(SpecChange(kind="add_measure", detail="just because"))
    assert result(spec, catalog, "RULE-008").status == "block"


def test_rule_008_fixture_changes_all_cite_ids(spec, catalog):
    assert result(spec, catalog, "RULE-008").status == "pass"


# FOCUS
def test_focus_too_many_visuals_cards_and_pages_warn(spec, catalog):
    spec.pages[0].visuals += [Visual(type="card", title=f"Extra {i}", measures=["Net Sales"]) for i in range(3)]
    spec.pages += [Page(name="Two"), Page(name="Three")]
    r = result(spec, catalog, "FOCUS")
    assert r.status == "warn" and "KPI cards" in r.message and "pages" in r.message and "visuals" in r.message


def test_focus_fixture_passes(spec, catalog):
    assert result(spec, catalog, "FOCUS").status == "pass"


# DATA
def test_data_gap_with_numbers_or_a_chart_blocks(spec, catalog):
    spec.measures.append(
        Measure(name="Gross-to-Net", kpi_id="KPI-034", expression="SUM(x)", feasible=False, gap_reason="")
    )
    spec.pages[0].visuals.append(Visual(type="line", title="GTN trend", measures=["Gross-to-Net"], dimension="month"))
    r = result(spec, catalog, "DATA")
    assert r.status == "block" and "no reason" in r.message and "expression" in r.message and "gap card" in r.message


def test_data_labelled_gap_shown_as_a_card_passes(spec, catalog):
    spec.measures.append(
        Measure(
            name="Gross-to-Net", kpi_id="KPI-034", expression="", feasible=False, gap_reason="no governed source data"
        )
    )
    spec.pages[0].visuals[3] = Visual(type="card", title="Gross-to-net", measures=["Gross-to-Net"])
    assert result(spec, catalog, "DATA").status == "pass"
