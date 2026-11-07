"""Off-topic first message ("yo mom"): the interview says it did not catch a business question instead of
asking "which medicines?". Works with the LLM off and with a model that misbehaves (the code decides WHAT is asked)."""
from dataclasses import replace
from datetime import date

import pytest

from steward import Steward
from steward.config import Settings
from steward.interview import CLARIFY_TEXT, Interviewer

pytestmark = pytest.mark.filterwarnings("ignore")

JUNK = ["yo mom", "asdf", "thanks!", "lol", "hello there"]


class FakeLLM:
    def __init__(self, *replies):
        self.replies = list(replies)

    def generate_json(self, prompt: str) -> dict:
        return self.replies.pop(0)


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("STEWARD_CATALOG", "datapack")
    settings = replace(
        Settings.from_env(), use_llm="off", data_dir=tmp_path_factory.mktemp("offtopic"), as_of=date(2026, 11, 6)
    )
    yield Steward(settings=settings), settings.prompts_dir
    mp.undo()


def offline(pack) -> Interviewer:
    return pack[0].interviewer


def with_llm(pack, *replies) -> Interviewer:
    steward, prompts = pack
    return Interviewer(steward.catalog, FakeLLM(*replies), prompts)


@pytest.mark.parametrize("text", JUNK)
def test_offline_junk_gets_a_clarify_not_a_scope_question(pack, text):
    state = offline(pack).start(text)
    assert state.last_asked == "clarify" and not state.done
    assert "which medicines should it cover" not in state.question.lower()
    assert state.questions_asked == 0  # a clarify does not use up the question budget
    assert state.options  # one-click ways in, so the user is not left at a blank box


def test_llm_that_asks_the_scope_question_anyway_is_overruled_by_the_code(pack):
    llm_says = {
        "intent": {"unmapped_terms": ["yo", "mom"], "confidence": {}},
        "next_question": "Which medicines should it cover?", "asks_about": "products",
    }
    state = with_llm(pack, llm_says).start("yo mom")
    assert state.last_asked == "clarify"
    assert state.question == CLARIFY_TEXT


def test_llm_wording_is_used_when_it_asks_for_the_clarification(pack):
    llm_says = {
        "intent": {"unmapped_terms": ["yo", "mom"], "confidence": {}},
        "next_question": "I didn't catch that. Try: how is Plant-B running?", "asks_about": "clarify",
    }
    state = with_llm(pack, llm_says).start("yo mom")
    assert state.question == "I didn't catch that. Try: how is Plant-B running?"


def test_after_a_clarify_a_real_request_goes_on_as_usual(pack):
    iv = offline(pack)
    state = iv.start("yo mom")
    state = iv.answer(state, "sorry, wrong chat, I need the efficiency")
    assert state.last_asked == "sites" and state.question == "Which site do you mean?"
    assert state.intent.theme == "plant_efficiency"
    assert state.intent.text.startswith("sorry, wrong chat")  # the junk is not the request
    assert "yo" not in state.intent.unmapped_terms and "mom" not in state.intent.unmapped_terms
    assert state.questions_asked == 1  # only the site question counted


def test_a_named_metric_after_a_clarify_asks_the_normal_scope_questions(pack):
    iv = offline(pack)
    state = iv.answer(iv.start("asdf"), "net sales for Xarelto")
    assert state.last_asked == "markets"


def test_repeated_junk_ends_the_interview_without_inventing_a_request(pack):
    iv = offline(pack)
    state = iv.start("yo mom")
    state = iv.answer(state, "lol")
    assert state.last_asked == "clarify" and state.question.startswith("Sorry, still not clear.")
    state = iv.answer(state, "hehe")
    assert state.done
    intent = state.intent
    assert not (intent.metric_ids or intent.products or intent.markets or intent.sites or intent.theme)


def test_skip_on_junk_does_not_build_a_default_dashboard(pack):
    iv = offline(pack)
    intent = iv.finish_with_defaults(iv.start("yo mom")).intent
    assert not intent.metric_ids and not intent.products and not intent.theme


@pytest.mark.parametrize(
    "text, first",
    [
        ("net sales", "markets"),  # a metric: not off topic
        ("Aspirin in Germany", "products"),  # a market: not off topic
        ("I need some numbers", "products"),  # nothing unmapped: the usual first question
        ("how is plant B doing", "metric_ids"),  # a site
    ],
)
def test_real_requests_are_not_mistaken_for_junk(pack, text, first):
    state = offline(pack).start(text)
    assert state.last_asked != "clarify", state.question
