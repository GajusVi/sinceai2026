"""AI-first investigation: the LLM's trail is grounded (ids and numbers from the dossier) and advisory (never the verdict)."""

from dataclasses import replace
from datetime import date

import pytest

from steward import Steward
from steward.config import Settings
from steward.investigate import dossier, investigate, validate

pytestmark = pytest.mark.filterwarnings("ignore")
REQ1 = "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country."


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("STEWARD_CATALOG", "datapack")
    s = Steward(
        settings=replace(
            Settings.from_env(), use_llm="off", data_dir=tmp_path_factory.mktemp("i"), as_of=date(2026, 11, 6)
        )
    )
    yield s, s.ask(REQ1)
    mp.undo()


class FakeLLM:
    provider = "fake"

    def __init__(self, raw):
        self.raw = raw

    def generate_json(self, prompt):
        self.prompt = prompt
        return self.raw


def test_dossier_lists_candidates_estate_and_rules(result):
    s, r = result
    estate = [a for a in s.catalog.active_artifacts() if a.product_scope == "Nubeqa"]
    text = dossier(r.decision, estate, ["KPI-023 Patient share"])
    assert r.decision.best.artifact.id in text and "still missing" in text
    assert "Other assets of the requested product(s)" in text and "KPI-023 Patient share" in text


def test_grounded_steps_are_kept_and_invented_ones_dropped(result):
    s, r = result
    best = r.decision.best.artifact
    facts = dossier(r.decision)
    raw = {
        "steps": [
            {"finding": f"{best.id} covers 60% of the request.", "record_ids": [best.id]},
            {"finding": "AST-9999 is perfect.", "record_ids": ["AST-9999"]},  # unknown id
            {"finding": f"{best.id} has 4321 users a month.", "record_ids": [best.id]},  # invented number
        ],
        "recommendation": "extend",
        "best_asset_id": best.id,
        "why": "It already has most of it.",
    }
    inv = validate(raw, facts, r.decision)
    assert [st.record_ids for st in inv.steps] == [[best.id]] and inv.dropped_steps == 2
    assert inv.recommendation == "EXTEND" and inv.agrees and inv.best_asset_id == best.id


def test_a_different_starting_asset_is_a_disagreement(result):
    s, r = result
    other = r.decision.alternatives[0].artifact.id
    raw = {
        "steps": [{"finding": f"{other} is closer.", "record_ids": [other]}],
        "recommendation": "EXTEND",
        "best_asset_id": other,
    }
    inv = validate(raw, dossier(r.decision), r.decision)
    assert not inv.agrees and inv.best_asset_id == other


def test_no_llm_or_nothing_grounded_gives_no_trail(result):
    s, r = result
    assert investigate(None, s.settings.prompts_dir, REQ1, "", r.decision) is None
    fake = FakeLLM({"steps": [{"finding": "AST-9999 wins.", "record_ids": ["AST-9999"]}]})
    assert investigate(fake, s.settings.prompts_dir, REQ1, "", r.decision) is None
    assert "<<<DATA" in fake.prompt and r.decision.verdict.value in fake.prompt
