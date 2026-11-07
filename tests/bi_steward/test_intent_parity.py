"""Audit F1 (DECISION T1.2): the interview path must reach the same verdict and asset as the rules path.

The Intent keeps display names ("Xarelto"); assets carry ids ("P-XAR"). Before the fix the adapter passed names,
so every product-locked asset looked incompatible and existing reports became CREATE on the main UI path."""
from dataclasses import replace
from datetime import date

import pytest

from steward import Steward
from steward.config import Settings
from steward.intent import Intent, value_id

pytestmark = pytest.mark.filterwarnings("ignore")
TEMPLATES = ["{p} net sales in Germany", "{p} net sales by month", "{p} on-time in-full"]


@pytest.fixture(scope="module")
def steward(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("STEWARD_CATALOG", "datapack")
    data_dir = tmp_path_factory.mktemp("parity")
    yield Steward(settings=replace(Settings.from_env(), use_llm="off", data_dir=data_dir, as_of=date(2026, 11, 6)))
    mp.undo()


def _interview(steward, text):
    state = steward.interviewer.start(text)
    while not state.done:
        state = steward.interviewer.finish_with_defaults(state)
    return steward.ask_intent(state.intent).decision


def _key(decision):
    return decision.verdict.value, decision.best.artifact.id if decision.best else None


def test_names_become_ids_at_the_boundary(steward):
    assert value_id(steward.catalog, "product", "Xarelto") == "P-XAR"
    assert value_id(steward.catalog, "market", "germany") == "DE"
    assert value_id(steward.catalog, "product", "Unknownium") == "Unknownium"  # never dropped silently
    q = Intent(text="Xarelto net sales in Germany", products=["Xarelto"], markets=["DE"], metric_ids=["net_sales"])
    assert q.to_parsed_question(steward.catalog).filters == {"product": "P-XAR", "market": "DE"}
    assert q.to_parsed_question(steward.catalog).dimensions == []  # no time breakdown unless asked
    every = Intent(text="All Pharma net sales by month", products=["All Pharma"], metric_ids=["net_sales"])
    parsed = every.to_parsed_question(steward.catalog)
    assert "product" not in parsed.filters and parsed.dimensions == ["month"]


def test_xarelto_germany_is_reused_on_the_interview_path(steward):
    assert _key(_interview(steward, "Xarelto net sales in Germany")) == ("REUSE", "AST-0191")


def test_both_paths_agree_on_every_product(steward):
    products = [v.label for v in steward.catalog.dimensions["product"].values]
    disagree = []
    for p in products:
        for t in TEMPLATES:
            text = t.format(p=p)
            rules, interview = _key(steward.ask(text).decision), _key(_interview(steward, text))
            if rules != interview:
                disagree.append((text, rules, interview))
    assert not disagree, disagree


def test_expired_provisional_assets_are_dropped_on_the_data_pack(tmp_path, monkeypatch):
    """T1.6 (C4/A4): load_catalog passes as_of, so a provisional asset past expires_at leaves the catalog."""
    import json
    from datetime import timedelta

    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    base = Steward(settings=replace(Settings.from_env(), use_llm="off", data_dir=tmp_path, as_of=date(2026, 11, 6)))
    template = json.loads(base.catalog.artifacts["AST-0191"].model_dump_json())
    rows = []
    for new_id, days in (("AST-0191-old", -1), ("AST-0191-new", 10)):
        rows.append({**template, "id": new_id, "status": "provisional",
                     "expires_at": str(date(2026, 11, 6) + timedelta(days=days))})
    (tmp_path / "catalog_changes.json").write_text(json.dumps({"added": rows, "superseded": []}))
    s = Steward(settings=replace(Settings.from_env(), use_llm="off", data_dir=tmp_path, as_of=date(2026, 11, 6)))
    assert "AST-0191-old" not in s.catalog.artifacts and "AST-0191-new" in s.catalog.artifacts
