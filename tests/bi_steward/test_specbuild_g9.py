"""G9: CONSOLIDATE, MIGRATE and RESCUE specs. Each passes lint or fails for the right reason.

None of the 150 requests reaches these verdicts in rules mode, so the decisions are real data-pack ones with the
verdict or the asset's state changed the way the engine would change it (cluster evidence, Tableau base, owner gone).
"""

from dataclasses import replace
from datetime import date

import pytest

from steward import Steward
from steward.config import Settings
from steward.intent import intent_from_parsed
from steward.lint import LOW_USE_USERS, _avg_users, lint
from steward.models import Evidence, Verdict
from steward.semantic import feasibility
from steward.specbuild import best_model, build_spec, spec_hash

pytestmark = pytest.mark.filterwarnings("ignore")

REQ1 = "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country."
EYLEA = "Net sales for Eylea in Japan"


@pytest.fixture(scope="module")
def steward(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("STEWARD_CATALOG", "datapack")
    data_dir = tmp_path_factory.mktemp("g9")
    yield Steward(settings=replace(Settings.from_env(), use_llm="off", data_dir=data_dir, as_of=date(2026, 11, 6)))
    mp.undo()


def build(steward, result, decision):
    intent = intent_from_parsed(result.question, steward.catalog)
    spec = build_spec(decision, intent, steward.catalog, feasibility(intent))
    spec.lint = lint(spec, steward.catalog)
    return spec


def rule(spec, rule_id):
    return next(r for r in spec.lint if r.rule_id == rule_id)


def with_best(decision, artifact, **update):
    return decision.model_copy(update={"best": decision.best.model_copy(update={"artifact": artifact}), **update})


def consolidate(decision, other_id):
    cluster = Evidence(
        claim=f"{other_id} duplicates the keeper",
        rule_id="RULE-001",
        record_ids=[other_id, decision.best.artifact.id],
        severity="warning",
    )
    return decision.model_copy(update={"verdict": Verdict.CONSOLIDATE, "evidence": [*decision.evidence, cluster]})


def test_consolidate_merges_the_duplicate_and_lists_its_downstream_impact(steward):
    result = steward.ask(REQ1)
    other = next(c.artifact for c in result.decision.alternatives if c.artifact.downstream_ids)
    spec = build(steward, result, consolidate(result.decision, other.id))
    keeper = result.decision.best.artifact
    assert spec.change_type == "consolidate" and spec.base_asset_ids == [keeper.id, other.id]
    merge = [c for c in spec.changes if c.kind == "merge_from"]
    assert len(merge) == 1 and set(other.downstream_ids) <= set(merge[0].record_ids)
    assert rule(spec, "RULE-004").status != "block"  # the retirement's downstream impact is covered
    assert {"KPI-004", "KPI-042"} <= set(spec.kpi_ids) and sum(v.type == "card" for v in spec.pages[0].visuals) <= 4
    assert spec.version == keeper.version + 1 and spec.provenance["spec_hash"] == spec_hash(spec)


def test_consolidate_without_the_merge_is_blocked_by_lineage(steward):
    result = steward.ask(REQ1)
    other = next(c.artifact for c in result.decision.alternatives if c.artifact.downstream_ids)
    spec = build(steward, result, consolidate(result.decision, other.id))
    spec.changes = [c for c in spec.changes if c.kind != "merge_from"]
    spec.lint = lint(spec, steward.catalog)
    r004 = rule(spec, "RULE-004")  # retiring it would orphan its downstream
    assert r004.status == "block" and other.id in r004.record_ids


def test_migrate_rebuilds_a_tableau_asset_in_power_bi(steward):
    result = steward.ask(REQ1)
    tableau = result.decision.best.artifact.model_copy(update={"platform": "Tableau"})
    decision = with_best(result.decision, tableau, flags=["MIGRATE"])
    spec = build(steward, result, decision)
    intent = intent_from_parsed(result.question, steward.catalog)
    assert spec.change_type == "migrate" and spec.platform == "Power BI"
    assert spec.source_model_id == best_model(intent)["model_id"]
    assert any(c.kind == "migrate_platform" and tableau.id in c.record_ids for c in spec.changes)
    r006 = rule(spec, "RULE-006")
    assert r006.status == "pass" or "low use" in r006.message or "not merged" in r006.message
    assert "canonical KPIs only; found" not in r006.message  # semantic-layer measures are canonical


def test_migrate_of_a_low_use_workbook_is_blocked(steward):
    result = steward.ask(REQ1)
    tableau = result.decision.best.artifact.model_copy(update={"platform": "Tableau"})
    assert _avg_users(steward.catalog.artifacts[tableau.id]) < LOW_USE_USERS  # lint reads usage from the catalog
    spec = build(steward, result, with_best(result.decision, tableau, flags=["MIGRATE"]))
    r006 = rule(spec, "RULE-006")
    assert r006.status == "block" and "low use" in r006.message and tableau.id in r006.record_ids


def test_rescue_reuses_the_asset_with_a_successor_owner(steward):
    result = steward.ask(EYLEA)
    assert result.decision.verdict == Verdict.REUSE
    successor = result.decision.alternatives[0].artifact.owner_id
    gone = result.decision.best.artifact.model_copy(
        update={"owner_status": "inactive", "successor_candidates": [successor]}
    )
    spec = build(steward, result, with_best(result.decision, gone))
    assert spec.change_type == "rescue" and spec.owner_id == successor and spec.version == gone.version + 1
    change = next(c for c in spec.changes if c.kind == "assign_owner")
    assert change.record_ids == [gone.id, gone.owner_id, successor] and "must accept" in change.detail
    assert rule(spec, "RULE-003").status == "pass"


def test_rescue_without_a_successor_is_blocked_until_a_human_assigns_one(steward):
    result = steward.ask(EYLEA)
    gone = result.decision.best.artifact.model_copy(update={"owner_status": "inactive", "successor_candidates": []})
    spec = build(steward, result, with_best(result.decision, gone))
    assert spec.change_type == "rescue" and spec.owner_id == ""
    assert rule(spec, "RULE-003").status == "block"
    assert "a human must assign one" in next(c.detail for c in spec.changes if c.kind == "assign_owner")
