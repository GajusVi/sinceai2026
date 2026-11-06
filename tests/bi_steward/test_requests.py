"""Decision T6 (option C): conflicts between request text and metadata have a severity. Targets all 40 hand-checked labels."""
import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from steward import Steward
from steward.config import Settings
from steward.requests import context_conflicts, load_requests, severity_of

pytestmark = pytest.mark.filterwarnings("ignore")

HOLDOUT = Path(__file__).resolve().parents[2] / "data" / "holdout" / "requests_intent.jsonl"
# Gajus, T6 decision. Used until Martynas adds metadata_severity to the jsonl; the label wins once it is there.
DECIDED = {
    "REQ-0009": "blocker", "REQ-0048": "blocker",
    "REQ-0010": "confirm", "REQ-0028": "confirm", "REQ-0040": "confirm", "REQ-0049": "confirm",
    "REQ-0002": "confirm",  # All Pharma context vs a named product: broader metadata, not a contradiction
    "REQ-0038": "none",  # country-level text inside an APAC context is consistent
}


@pytest.fixture(scope="module")
def steward(tmp_path_factory) -> Steward:
    mp = pytest.MonkeyPatch()
    mp.setenv("STEWARD_CATALOG", "datapack")
    settings = replace(Settings.from_env(), use_llm="off", data_dir=tmp_path_factory.mktemp("s"), as_of=date(2026, 11, 6))
    yield Steward(settings=settings)
    mp.undo()


def _rows():
    return [json.loads(line) for line in HOLDOUT.read_text(encoding="utf-8").splitlines() if line.strip()]


def _expected(row) -> str:
    if "metadata_severity" in row:
        return row["metadata_severity"]
    if row["request_id"] in DECIDED:
        return DECIDED[row["request_id"]]
    return "blocker" if row["metadata_conflict"] else "none"


def test_all_40_labels(steward):
    requests = {r.request_id: r for r in load_requests()}
    wrong = []
    for row in _rows():
        r = requests[row["request_id"]]
        got = severity_of(context_conflicts(r.text, r.context, steward.catalog))
        if got != _expected(row):
            wrong.append((row["request_id"], _expected(row), got, r.product_context, r.market_context))
    assert len(_rows()) == 40
    assert not wrong, wrong


def test_therapeutic_area_maps_to_product_set(steward):
    text = "dashboard across oncology brands"
    assert severity_of(context_conflicts(text, {"product": "Beyonttra", "market": "Global"}, steward.catalog)) == "blocker"
    assert context_conflicts(text, {"product": "Hyrnuo", "market": "Global"}, steward.catalog) == []  # a member of the set
    assert severity_of(context_conflicts(text, {"product": "All Pharma", "market": "Global"}, steward.catalog)) == "confirm"


def test_global_text_vs_region_context_is_a_blocker_and_global_context_is_fine(steward):
    assert severity_of(context_conflicts("global Nubeqa dashboard", {"product": "Nubeqa", "market": "EMEA"}, steward.catalog)) == "blocker"
    assert context_conflicts("global Nubeqa dashboard", {"product": "Nubeqa", "market": "Global"}, steward.catalog) == []


def test_blocker_forces_clarify_confirm_only_warns(steward):
    blocked = steward.ask("Create a global Nubeqa dashboard showing net sales", {"product": "Nubeqa", "market": "EMEA"})
    assert blocked.decision.verdict.value == "CLARIFY"
    assert any(e.severity == "blocker" and "global" in e.claim for e in blocked.decision.evidence)

    text = "Show net sales for Bayer Pharma by month"
    plain = steward.ask(text).decision
    warned = steward.ask(text, {"product": "Nubeqa", "market": "Global"})
    assert warned.decision.verdict == plain.verdict  # the verdict follows the text
    assert warned.question.conflicts == []
    assert any(e.severity == "warning" and "Bayer Pharma" in e.claim for e in warned.decision.evidence)
