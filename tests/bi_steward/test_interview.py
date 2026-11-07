"""G2: three scripted conversations with a fake model produce valid, complete Intents; the code enforces the rules."""
from dataclasses import replace
from datetime import date

import pytest

from steward import Steward
from steward.config import Settings
from steward.interview import Interviewer

pytestmark = pytest.mark.filterwarnings("ignore")

CONF = {"products": 0.9, "markets": 0.9, "metric_ids": 0.9, "decision_supported": 0.8}


class FakeLLM:
    """Returns canned JSON, one per call, and remembers the prompts it was given."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.prompts: list[str] = []

    def generate_json(self, prompt: str) -> dict:
        self.prompts.append(prompt)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("STEWARD_CATALOG", "datapack")
    data_dir = tmp_path_factory.mktemp("s")
    settings = replace(Settings.from_env(), use_llm="off", data_dir=data_dir, as_of=date(2026, 11, 6))
    yield Steward(settings=settings), settings.prompts_dir
    mp.undo()


def interviewer(pack, llm):
    steward, prompts = pack
    return Interviewer(steward.catalog, llm, prompts)


def test_conversation_1_supply_planner_novice(pack):
    llm = FakeLLM(
        {"intent": {"metric_ids": ["inventory_coverage"], "confidence": {"metric_ids": 0.8}},
         "next_question": "Which medicine and which countries do you check first when stock looks thin?"},
        {"intent": {"metric_ids": ["inventory_coverage"], "products": ["Xarelto"], "markets": ["DE"],
                    "confidence": {"metric_ids": 0.8, "products": 0.95, "markets": 0.95}},
         "next_question": "What will you decide with it?"},
        {"intent": {"role": "supply planner", "metric_ids": ["inventory_coverage"], "products": ["Xarelto"],
                    "markets": ["DE"], "decision_supported": "weekly supply meeting: reorder or not",
                    "cadence": "weekly", "confidence": CONF},
         "next_question": None},
    )
    iv = interviewer(pack, llm)
    state = iv.start("I need to keep an eye on stock")
    assert state.question and not state.done
    state = iv.answer(state, "Xarelto in Germany")
    assert state.question
    state = iv.answer(state, "it feeds the weekly supply meeting, we decide whether to reorder")
    assert state.done and state.intent.is_complete() and state.questions_asked == 2
    parsed = state.intent.to_parsed_question()
    assert parsed.metrics == ["inventory_coverage"] and parsed.filters == {"product": "Xarelto", "market": "DE"}


def test_conversation_2_conflict_is_asked_then_cleared(pack):
    conflict = "blocker: the text names Nubeqa, the request metadata says Beyonttra"
    llm = FakeLLM(
        {"intent": {"products": ["Nubeqa"], "markets": ["Global"], "metric_ids": ["net_sales_growth"],
                    "decision_supported": "launch review", "conflicts": [conflict], "confidence": CONF},
         "next_question": "You wrote Nubeqa but the request form says Beyonttra. Which one is it?"},
        {"intent": {"products": ["Nubeqa"], "markets": ["Global"], "metric_ids": ["net_sales_growth"],
                    "decision_supported": "launch review", "conflicts": [], "confidence": CONF},
         "next_question": None},
    )
    iv = interviewer(pack, llm)
    state = iv.start("Create a global Nubeqa dashboard showing sales growth", conflicts=[conflict])
    assert not state.done and "Beyonttra" in state.question and state.last_asked == "conflict"
    assert conflict in llm.prompts[0]
    state = iv.answer(state, "Nubeqa, the form is wrong")
    assert state.done and state.intent.is_complete() and state.intent.conflicts == []
    assert state.intent.to_parsed_question().filters["market"] == "Global"


def test_conversation_3_expert_mode_does_not_interview(pack):
    llm = FakeLLM({"intent": {"products": ["Eylea"], "markets": ["JP"], "metric_ids": ["net_sales"]},
                   "next_question": "What will you decide?"})  # the model asks anyway: the code overrules it
    state = interviewer(pack, llm).start("Net sales for Eylea in Japan", mode="expert")
    assert state.done and state.question is None and state.intent.mode == "expert"


def test_ids_outside_the_dictionary_become_unmapped_terms(pack):
    llm = FakeLLM({"intent": {"metric_ids": ["batch_yield", "net_sales"], "products": ["Aspirin", "nubeqa"],
                              "markets": ["de", "Narnia"],
                              "confidence": {"products": 7, "markets": -1, "metric_ids": "high"}},
                   "next_question": None})
    intent = interviewer(pack, llm).start("batch yield for Aspirin").intent
    assert intent.metric_ids == ["net_sales"] and intent.products == ["Nubeqa"] and intent.markets == ["DE"]
    assert set(intent.unmapped_terms) == {"batch_yield", "Aspirin", "Narnia"}
    assert intent.confidence == {"products": 1.0, "markets": 0.0}  # clipped; non-numbers dropped


def test_question_cap_stops_a_model_that_never_finishes(pack):
    llm = FakeLLM(*[{"intent": {}, "next_question": "Anything else?"}] * 8)
    iv = interviewer(pack, llm)
    state = iv.start("something vague")
    while not state.done:
        state = iv.answer(state, "dunno")
    assert state.questions_asked == 5


def test_prompt_renders_with_dictionary_and_bank(pack):
    llm = FakeLLM({"intent": {}, "next_question": None})
    interviewer(pack, llm).start("net sales")
    prompt = llm.prompts[0]
    assert "net_sales: Net Sales" in prompt and "Nubeqa" in prompt and "launch readiness" in prompt
    assert "supply" in prompt and "{dictionary}" not in prompt and "{{" not in prompt


def test_no_llm_or_llm_failure_falls_back_to_rules_and_fixed_questions(pack):
    for llm in (None, FakeLLM(RuntimeError("boom"), RuntimeError("boom"), RuntimeError("boom"))):
        iv = interviewer(pack, llm)
        state = iv.start("Net sales for Nubeqa")
        assert state.last_asked == "markets" and "country or region" in state.question
        state = iv.answer(state, "Germany")
        assert state.last_asked == "decision_supported"
        state = iv.answer(state, "the monthly review with the finance director")
        assert state.done and state.intent.is_complete()
        assert state.intent.products == ["Nubeqa"] and state.intent.markets == ["DE"]
