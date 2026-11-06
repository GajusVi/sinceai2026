"""Verdict contract on the Bayer data pack (the sample-catalog contract stays in test_golden.py)."""
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from steward import Steward
from steward.config import Settings
from steward.linking import find_terms
from steward.requests import context_conflicts, load_requests

AS_OF = date(2026, 11, 6)

pytestmark = pytest.mark.filterwarnings("ignore")

GOLDEN = json.loads((Path(__file__).parent / "golden_datapack.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pack_steward(tmp_path_factory) -> Steward:
    mp = pytest.MonkeyPatch()
    mp.setenv("STEWARD_CATALOG", "datapack")
    settings = replace(Settings.from_env(), use_llm="off", data_dir=tmp_path_factory.mktemp("steward"), as_of=AS_OF)
    yield Steward(settings=settings)
    mp.undo()


@pytest.mark.parametrize("case", GOLDEN, ids=[c["question"][:60] + ("|ctx" if "context" in c else "") for c in GOLDEN])
def test_golden_question(pack_steward, case):
    if case.get("known_gap"):
        pytest.xfail(case["known_gap"])
    decision = pack_steward.ask(case["question"], case.get("context")).decision

    assert decision.verdict.value == case["verdict"]
    best_id = decision.best.artifact.id if decision.best else None
    assert best_id == case["artifact_id"]
    if "official_kpis" in case:
        assert {c.official_formula for c in decision.conflicts} == set(case["official_kpis"])
    if "variant_kpis" in case:
        assert set(case["variant_kpis"]) <= {c.artifact_formula for c in decision.conflicts}
    if "context" in case:
        assert any(e.severity == "blocker" and "metadata" in e.claim for e in decision.evidence)


def test_known_gap_cases_still_fail(pack_steward):
    """When a known gap is fixed this fails: remove its known_gap key so the golden starts guarding it."""
    for case in (c for c in GOLDEN if c.get("known_gap")):
        assert pack_steward.ask(case["question"]).decision.verdict.value != case["verdict"], case["question"]


def test_request_metadata_contradicts_text_in_65_of_75(pack_steward):
    """Trap 1 from the data pack doc: 75 requests name a product, 65 of them carry a different product_context."""
    catalog = pack_steward.catalog
    named = flagged = 0
    for r in load_requests():
        if any(t.kind == "value" and t.dimension == "product" for t in find_terms(r.text, catalog)):
            named += 1
            flagged += any(r.product_context in c for c in context_conflicts(r.text, r.context, catalog))
    assert (named, flagged) == (75, 65)


def test_consistent_request_has_no_conflict(pack_steward):
    assert context_conflicts("Net sales for Nubeqa in Germany", {"product": "Nubeqa", "market": "EMEA"}, pack_steward.catalog) == []
