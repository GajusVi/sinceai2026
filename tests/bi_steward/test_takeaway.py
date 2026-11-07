"""AI takeaway: the model may only quote numbers the rendered dashboard computed."""

import pandas as pd

from steward.render import CardView, GapView, RenderedDashboard
from steward.takeaway import facts, takeaway, validate


def dashboard():
    return RenderedDashboard(
        title="Nubeqa",
        cards=[CardView("Net sales", "KPI-001", "EUR 3,347.7 M", "-1.5% vs forecast")],
        gaps=[GapView("Patient share", "KPI-023", "Patient share", "no source data")],
        tables=[("Countries off forecast", pd.DataFrame({"Country": ["Germany"], "Off forecast (%)": [-12.3]}))],
    )


def test_facts_carry_cards_gaps_and_tables():
    text = facts(dashboard())
    assert "EUR 3,347.7 M" in text and "GAP" in text and "Germany" in text and "-12.3" in text


def test_only_computed_numbers_pass():
    known = facts(dashboard())
    assert validate("Net sales are EUR 3,347.7 M, 1.5% under forecast; Germany is 12.3% off.", known)
    assert validate("Net sales are EUR 3.3 billion.", known) == ""  # rounded = invented
    assert validate("Sales grew 7% in Germany.", known) == ""


class FakeLLM:
    def __init__(self, text):
        self.text = text

    def generate_json(self, prompt):
        assert "<<<DATA" in prompt and "EUR 3,347.7 M" in prompt
        return {"takeaway": self.text}


def test_takeaway_uses_the_llm_and_rejects_invented_numbers(tmp_path):
    from steward.config import ROOT_DIR

    prompts = ROOT_DIR / "prompts"
    assert takeaway(FakeLLM("Net sales EUR 3,347.7 M."), prompts, "q", dashboard()) == "Net sales EUR 3,347.7 M."
    assert takeaway(FakeLLM("Net sales EUR 9,999 M."), prompts, "q", dashboard()) == ""
    assert takeaway(None, prompts, "q", dashboard()) == ""
