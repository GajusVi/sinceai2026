import json
from datetime import date
from types import SimpleNamespace

import pytest

from steward.catalog import Catalog
from steward.config import ROOT_DIR
from steward.datapack import load_artifacts
from steward.decision.conflicts import find_conflicts
from steward.decision.engine import decide
from steward.linking import artifact_covered_metrics
from steward.models import DimensionDefinition, MetricDefinition, ParsedQuestion
from steward.query_parser import RuleBasedParser
from steward.search import CatalogSearch

pytestmark = pytest.mark.filterwarnings("ignore")


AS_OF = date(2026, 11, 6)
BAYER = ROOT_DIR / "catalog" / "bayer"


class Pack:
    """Data-pack catalog built by hand, so these tests do not depend on Steward's catalog switch."""

    def __init__(self):
        read = lambda name: json.loads((BAYER / name).read_text(encoding="utf-8"))  # noqa: E731
        self.catalog = Catalog(
            load_artifacts(),
            [MetricDefinition.model_validate(m) for m in read("metrics.json")],
            [DimensionDefinition.model_validate(d) for d in read("dimensions.json")],
        )
        self.search = CatalogSearch(self.catalog, None)

    def ask(self, text):
        question = RuleBasedParser(self.catalog).parse(text)
        return SimpleNamespace(question=question, decision=decide(question, self.search.search(question), self.catalog, AS_OF))


@pytest.fixture(scope="module")
def pack():
    return Pack()


def test_variant_kpi_is_a_conflict_and_does_not_cover(pack):
    holders = [a for a in pack.catalog.active_artifacts() if {"KPI-018", "KPI-019"} & set(a.kpi_ids)]
    assert holders
    for a in holders:
        has_canonical = "KPI-016" in a.kpi_ids
        assert ("inventory_coverage" in artifact_covered_metrics(a, pack.catalog)) == has_canonical
    conflicts = find_conflicts(["inventory_coverage"], pack.catalog)
    assert {"KPI-018", "KPI-019"} <= {c.artifact_formula for c in conflicts}
    assert {c.official_formula for c in conflicts} == {"KPI-016"}


def test_decision_cites_rule_002_with_canonical_suggestion(pack):
    question = ParsedQuestion(text="inventory coverage", metrics=["inventory_coverage"])
    decision = decide(question, pack.search.search(question), pack.catalog, AS_OF)
    rule_002 = [e for e in decision.evidence if e.rule_id == "RULE-002"]
    assert rule_002 and all("KPI-016" in e.claim for e in rule_002)
    assert all(e.record_ids[0].startswith("AST-") for e in rule_002)


def test_sample_catalog_still_uses_formula_path(steward):
    assert all(not a.kpi_ids for a in steward.catalog.artifacts.values())
    assert steward.ask("Net revenue by region for Q3").decision.verdict.value == "REUSE"


REQ_0001 = "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country."


def test_req_0001_on_data_pack_extends_a_partial_match(pack):
    """Text alone: no asset carries all 3 canonical KPIs, so never REUSE. Search must surface assets with 1 of 3 (EXTEND)."""
    decision = pack.ask(REQ_0001).decision
    assert decision.verdict.value == "EXTEND"
    assert any(i.startswith("metric:") for i in decision.best.covered)
    assert {"AST-0015", "AST-0335"} & {c.artifact.id for c in [decision.best, *decision.alternatives]}


def test_req_0001_text_vs_metadata_conflict_is_clarify(pack):
    """Trap 1: the request metadata says Beyonttra/EMEA, the text says global Nubeqa. The conflict forces CLARIFY."""
    question = RuleBasedParser(pack.catalog).parse(REQ_0001)
    question.conflicts = ["text says global Nubeqa, request product_context says Beyonttra/EMEA"]
    decision = decide(question, pack.search.search(question), pack.catalog, AS_OF)
    assert decision.verdict.value == "CLARIFY"
    assert any(e.severity == "blocker" for e in decision.evidence)


def test_global_request_is_a_scope_filter_only_global_assets_are_compatible(pack):
    from steward.decision.engine import score_candidates

    question = RuleBasedParser(pack.catalog).parse("Net sales growth globally by market")
    assert question.filters.get("market") == "Global"
    candidates = score_candidates(question, pack.search.search(question), pack.catalog, AS_OF)
    assert candidates
    assert all(c.artifact.market_scope == "Global" for c in candidates if c.compatible)
    assert any(c.artifact.market_scope != "Global" and not c.compatible for c in candidates)


def test_req_0001_global_request_keeps_name_vs_scope_mismatch_asset_eligible(pack):
    """AST-0143 is named '... - EMEA' but market_scope is Global (trap 18): scope comes from the field, never the name."""
    decision = pack.ask(REQ_0001).decision
    assert decision.best.artifact.market_scope == "Global"
    by_id = {c.artifact.id: c for c in [decision.best, *decision.alternatives]}
    assert "AST-0143" in by_id and by_id["AST-0143"].compatible
    assert any(d.startswith("NAME_SCOPE_MISMATCH") for d in by_id["AST-0143"].artifact.data_quality)


def test_unrelated_text_gets_no_global_filter(pack):
    assert "market" not in RuleBasedParser(pack.catalog).parse("Net sales growth by month").filters


def test_trust_follows_build_plan_2_3_on_real_fields(pack):
    from steward.decision.signals import trust

    promoted = pack.catalog.artifact("AST-0019")  # Tableau, promoted, healthy model, active owner
    assert promoted.endorsement == "promoted" and promoted.refresh_status == "healthy" and promoted.owner_status == "active"
    assert trust(promoted, AS_OF) == 0.85  # .25 promoted + .20 owner + .25 refresh + .15 users (avg 51/month), no open high signal
    unendorsed = pack.catalog.artifact("AST-0191")  # Power BI, unendorsed, healthy, 103 users
    assert trust(unendorsed, AS_OF) == 0.6  # .20 owner + .25 refresh + .15 users (avg 65/month)


def test_tableau_is_never_reused_it_is_extended_with_migrate_flag(pack):
    from steward.search.engine import SearchHit

    question = ParsedQuestion(text="net sales", metrics=["net_sales"], filters={"product": "P-XAR", "market": "BR"}, dimensions=["month"])
    tableau = pack.catalog.artifact("AST-0019")
    hits = [SearchHit(tableau, 1.0, {})]
    decision = decide(question, hits, pack.catalog, AS_OF)
    assert decision.verdict.value == "EXTEND" and decision.best.artifact.id == "AST-0019"
    assert "MIGRATE" in decision.flags
    assert any(e.rule_id == "RULE-006" for e in decision.evidence)


def test_trust_is_rounded_so_float_noise_cannot_flip_the_reuse_threshold(pack):
    from steward.config import REUSE_MIN_TRUST
    from steward.decision.signals import trust

    value = trust(pack.catalog.artifact("AST-0191"), AS_OF)  # .20 + .25 + .15 sums to 0.6000000000000001 in floats
    assert value == round(value, 2) == 0.6
    assert value >= REUSE_MIN_TRUST
    assert all(trust(a, AS_OF) == round(trust(a, AS_OF), 2) for a in pack.catalog.active_artifacts())
