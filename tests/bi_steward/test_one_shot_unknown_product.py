"""One-shot AI path: a product the data pack does not know never builds (live Gemini run, Sat 22:30: 'Roundup sales in
Brazil' -> EXTEND AST-0019). The expert interview sets the unknown word aside as ignored_terms and leaves products empty,
which reads as All Pharma; _ask_ai must hand the question to the rules parser instead, which answers CLARIFY."""

from dataclasses import replace
from datetime import date

import pytest

from steward import Steward
from steward.config import Settings
from steward.intent import Intent
from steward.interview import InterviewState
from steward.models import Verdict

pytestmark = pytest.mark.filterwarnings("ignore")


class FakeLLM:
    provider = "fake"

    def generate_json(self, prompt):
        raise AssertionError("the interview is replaced in these tests; nothing else may call the model")


@pytest.fixture
def steward(tmp_path, monkeypatch):
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    s = Steward(settings=replace(Settings.from_env(), use_llm="off", data_dir=tmp_path, as_of=date(2026, 11, 6)))
    s.llm = FakeLLM()  # _ask_ai only runs with an LLM
    return s


def _model_read(steward, monkeypatch, **intent):
    """What the expert interview returned on Gemini for the question (the model's part, replayed)."""
    state = InterviewState(intent=Intent(**intent))
    monkeypatch.setattr(steward.interviewer, "start", lambda *a, **k: state)


@pytest.mark.parametrize(
    "text, word, market",
    [("Roundup sales in Brazil", "Roundup", "BR"), ("Net sales for Aspirin in Germany", "Aspirin", "DE")],
)
def test_unknown_product_set_aside_by_the_interview_gets_a_clarify(steward, monkeypatch, text, word, market):
    _model_read(steward, monkeypatch, markets=[market], metric_ids=["net_sales"], ignored_terms=[word])
    result = steward.ask(text)
    assert result.decision.verdict == Verdict.CLARIFY
    assert word in result.question.unmapped_terms
    assert "product" not in result.question.filters


def test_an_ignored_word_next_to_a_known_product_still_takes_the_ai_path(steward, monkeypatch):
    _model_read(steward, monkeypatch, products=["Xarelto"], markets=["BR"], metric_ids=["net_sales"], ignored_terms=["yo"])
    monkeypatch.setattr("steward.investigate.investigate", lambda *a, **k: None)
    seen = []
    original = steward.ask_intent
    monkeypatch.setattr(steward, "ask_intent", lambda intent, **k: seen.append(intent) or original(intent, **k))
    steward.ask("Xarelto net sales in Brazil yo")
    assert seen and seen[0].products == ["Xarelto"]
