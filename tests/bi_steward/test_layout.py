"""Dynamic layout (steward/layout.py): the LLM orders the story inside a role envelope; code validates; fallback."""
from dataclasses import replace
from datetime import date

import pytest

from steward import Steward, layout
from steward.auth import login
from steward.config import Settings
from steward.layout import ENVELOPES, Layouter, LayoutError, fit, plan
from steward.lint import can_approve
from steward.models import Verdict
from steward.spec import Visual
from steward.specbuild import _menu

pytestmark = pytest.mark.filterwarnings("ignore")

REQ1 = "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country."
GAP_REQ = "Nubeqa net sales, gross-to-net rate and on-time in-full in Germany"  # KPI-034 is governed, has no data


class FakeLLM:
    """Stands in for the model: returns what the test says, counts calls."""

    model = "fake-1"

    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.calls = reply, error, 0

    def generate_json(self, prompt):
        self.calls += 1
        if self.error:
            raise self.error
        return self.reply


@pytest.fixture(autouse=True)
def fresh_cache():
    layout._CACHE.clear()
    yield
    layout._CACHE.clear()


@pytest.fixture(scope="module")
def steward(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("STEWARD_CATALOG", "datapack")
    data_dir = tmp_path_factory.mktemp("layout")
    yield Steward(settings=replace(Settings.from_env(), use_llm="off", data_dir=data_dir, as_of=date(2026, 11, 6)))
    mp.undo()


def built(steward, text, llm=None, user=None):
    asked = steward.ask(text)  # without a model: the fake one answers the layout call only
    steward.llm = llm
    try:
        result = steward.build(asked, user=user)
    finally:
        steward.llm = None
    return result.spec


def types(spec):
    return [v.type for v in spec.pages[0].visuals]


def ids(spec):
    return [f"{v.type}:{v.measures[0]}" for v in spec.pages[0].visuals]


@pytest.fixture(scope="module")
def template(steward):
    return built(steward, REQ1)


def menu_ids(steward, text=REQ1):
    from steward.intent import intent_from_parsed

    spec = built(steward, text)
    intent = intent_from_parsed(steward.ask(text).question, steward.catalog)
    return spec, _menu(spec.measures, intent, steward.catalog, "market")  # spec.measures = asked + context measures


def steps(*pairs):
    reason = "Answer first, then where it comes from, so a reader never has to hunt for the next number to look at."
    return {"steps": [{"id": i, "question": q} for i, q in pairs], "reason": reason}


def test_offline_is_the_template_for_every_role(steward, template):
    assert template.provenance["layout_source"] == "template" and template.provenance["layout_role"] == "builder"
    assert types(template) == ["card"] * 4 + ["line", "bar", "table"]
    assert can_approve(template)
    for name, pw in (("Manager07", "Manage123"), ("Worker21", "Worker123")):
        spec = built(steward, REQ1, user=login(name, pw))
        assert spec.provenance["layout_source"] == "template"
        assert ENVELOPES[spec.provenance["layout_role"]].max_visuals >= len(types(spec))


def test_template_wording_is_plain(steward, template):
    purposes = " ".join(v.purpose for v in template.pages[0].visuals)
    assert "countrys" not in purposes and "Which countries drive it" in purposes


def test_llm_orders_the_story_and_writes_the_questions(steward, template):
    _, menu = menu_ids(steward)
    by_id = [o.id for o in menu]
    want = ["card:KPI-042", "card:KPI-001", "card:KPI-004", "card:KPI-027", "table:KPI-042", "line:KPI-001"]
    assert set(want) <= set(by_id)
    llm = FakeLLM(steps(*[(i, f"Question for {i.split(':')[0]}?") for i in want]))
    spec = built(steward, REQ1, llm)
    assert llm.calls == 1
    names = {"KPI-042": "Forecast Variance", "KPI-001": "Net Sales", "KPI-004": "Net Sales Growth",
             "KPI-027": "Market Access Coverage"}
    assert ids(spec) == [f"{i.split(':')[0]}:{names[i.split(':')[1]]}" for i in want]
    assert spec.provenance["layout_source"] == "llm" and spec.provenance["model"] == "fake-1"
    assert spec.pages[0].visuals[0].purpose == "Question for card?"
    if "step" in Visual.model_fields:  # Martynas's contract field: the position in the story
        assert [v.step for v in spec.pages[0].visuals] == list(range(1, len(want) + 1))
        assert spec.pages[0].visuals[0].question == "Question for card?"
    assert spec.provenance["layout_reason"].startswith("Answer first")
    assert can_approve(spec)  # the LLM layout still passes the lint gate
    # same measures, same numbers: the layout never changes what is measured
    assert {m.kpi_id for m in spec.measures} == {m.kpi_id for m in template.measures}


@pytest.mark.parametrize(
    "reply, error",
    [
        (None, RuntimeError("429")),
        ({"steps": []}, None),
        ({"nope": 1}, None),
        ("not json", None),
        ({"steps": [{"id": "pie:KPI-001"}, {"id": "bar:KPI-999"}, "x"]}, None),
    ],
)
def test_bad_proposals_fall_back_to_the_template(steward, template, reply, error):
    spec = built(steward, REQ1, FakeLLM(reply, error))
    assert spec.provenance["layout_source"] == "template" and "layout_fallback" in spec.provenance
    assert spec.pages == template.pages


def test_invalid_steps_are_dropped_and_asked_measures_stay(steward, template):
    # the model forgets three cards, repeats one, invents an id and puts a chart first: the answer still comes first
    llm = FakeLLM(steps(
        ("line:KPI-001", "When did it move?"), ("card:KPI-042", "Is it on forecast?"),
        ("card:KPI-042", "again"), ("card:KPI-777", "invented"),
    ))
    spec = built(steward, REQ1, llm)
    got = ids(spec)
    assert got[0] == "card:Forecast Variance" and got[-1] == "line:Net Sales"
    assert {"card:Net Sales", "card:Net Sales Growth", "card:Market Access Coverage"} <= set(got)  # forced back in
    assert len(got) == len(set(got))


def test_text_with_digits_or_ids_is_replaced_by_the_template_wording(steward):
    llm = FakeLLM(steps(("card:KPI-001", "Is net sales up 12%?"), ("line:KPI-001", "See KPI-001 over time?"),
                        ("bar:KPI-001", "Which countries drive it?")))
    spec = built(steward, REQ1, llm)
    purposes = {f"{v.type}": v.purpose for v in spec.pages[0].visuals}
    assert purposes["bar"] == "Which countries drive it?"  # clean text kept
    assert purposes["line"] == "See when it moved" and not any(c.isdigit() for p in purposes.values() for c in p)


def test_worker_envelope_holds_whatever_the_model_asks(steward):
    worker = login("Worker21", "Worker123")
    everything = [o.id for o in menu_ids(steward)[1]]
    spec = built(steward, REQ1, FakeLLM(steps(*[(i, "ok?") for i in everything])), user=worker)
    assert spec.provenance["layout_role"] == "worker" and spec.provenance["layout_source"] == "llm"
    env = ENVELOPES["worker"]
    assert len(types(spec)) <= env.max_visuals and types(spec).count("card") <= env.max_cards
    assert set(types(spec)) <= env.types  # no breakdown, no exceptions table on the floor view


def test_a_gap_stays_a_labelled_card_whatever_the_model_does(steward):
    plain = built(steward, GAP_REQ)
    gap = next(m for m in plain.measures if not m.feasible)
    assert gap.gap_reason
    # the model leaves the gap out and asks for every chart it can
    menu = menu_ids(steward, GAP_REQ)[1]
    asked = [o.id for o in menu if o.feasible or o.visual.type != "card"]
    spec = built(steward, GAP_REQ, FakeLLM(steps(*[(i, "ok?") for i in asked])))
    gap_visuals = [v for v in spec.pages[0].visuals if gap.name in v.measures]
    assert [v.type for v in gap_visuals] == ["card"]  # only ever a gap card, never a chart
    assert not [r for r in spec.lint if r.rule_id == "DATA" and r.status == "block"]


def test_plan_rejects_without_valid_steps(steward):
    spec, menu = menu_ids(steward)
    base = fit(spec.pages[0], ENVELOPES["builder"])
    with pytest.raises(LayoutError):
        plan({"steps": [{"id": "zzz"}]}, menu, base, ENVELOPES["builder"])


def test_the_same_proposal_is_asked_once(steward):
    llm = FakeLLM(steps(("card:KPI-001", "How big is it?")))
    first = built(steward, REQ1, llm)
    again = built(steward, REQ1, llm)
    assert llm.calls == 1 and first.pages == again.pages  # cached by prompt, so reruns are free and stable


def test_the_verdict_is_untouched_by_the_layout(steward):
    asked = steward.ask(REQ1)
    steward.llm = FakeLLM(None, RuntimeError("down"))
    try:
        result = steward.build(asked)
    finally:
        steward.llm = None
    assert result.decision.verdict == Verdict.EXTEND and result.spec is not None


def test_layouter_without_a_model_is_the_template():
    assert Layouter().info == {} and Layouter().role == "builder"
