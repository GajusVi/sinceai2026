"""T2.5 receipt strip: every step says what went in, what came out and why; the Decide line carries the gates."""
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from steward import Steward
from steward.auth import login
from steward.config import Settings
from steward.receipts import Meter, first_failure, receipts

pytestmark = pytest.mark.filterwarnings("ignore")
APP = str(Path(__file__).resolve().parents[2] / "frontend" / "steward_app.py")
BUILDER = login("Builder12", "Admin123")


@pytest.fixture(scope="module")
def steward(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("STEWARD_CATALOG", "datapack")
    yield Steward(settings=replace(Settings.from_env(), use_llm="off", data_dir=tmp_path_factory.mktemp("rc"),
                                   as_of=date(2026, 11, 6)))
    mp.undo()


def _run(steward, text):
    state = steward.interviewer.finish_with_defaults(steward.interviewer.start(text))
    result = steward.build(steward.ask_intent(state.intent), state.intent, BUILDER)
    return result, receipts(result, state.intent, steward.catalog, steward.as_of)


def test_reuse_passes_the_coverage_gates_and_names_the_certify_action(steward):
    result, rows = _run(steward, "Xarelto net sales in Germany")
    assert [r.step for r in rows][:3] == ["Understand", "Find what exists", "Decide"]
    decide = rows[2]
    assert decide.out == "REUSE" and decide.ids == ["AST-0191"]
    failed = [g.name for g in decide.gates if not g.ok]
    assert failed == ["Certified or promoted"] and "certify" in decide.why  # C2: an action, not a block


def test_extend_names_the_first_failing_gate(steward):
    result, rows = _run(steward, "Nubeqa net sales growth and forecast variance globally by country.")
    decide = next(r for r in rows if r.step == "Decide")
    assert decide.out == "EXTEND" and first_failure(decide.gates).name == "Has every requested KPI"
    assert "Forecast Variance" in decide.why


def test_the_meter_counts_ai_calls_per_phase():
    class Fake:
        def generate_json(self, prompt):
            return {}

    llm, phases = Fake(), {}
    meter = Meter(llm)
    with meter.phase("understand", into=phases):
        llm.generate_json("a")
        llm.generate_json("b")
    with meter.phase("build", into=phases):
        pass
    assert phases["understand"]["llm"] == 2 and phases["build"]["llm"] == 0 and phases["build"]["ms"] >= 0
    Meter(llm)  # wrapping twice must not double count
    with meter.phase("again", into=phases):
        llm.generate_json("c")
    assert phases["again"]["llm"] == 1


def test_the_app_shows_the_strip(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    st.cache_resource.clear()
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["user"] = BUILDER
    at.run()
    at.chat_input[0].set_value("Xarelto net sales in Germany").run()
    skip = [b for b in at.button if b.label == "Use recommended"]
    if skip:
        skip[0].click().run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "How this was decided" in text and "Find what exists" in text and "AST-0191" in text
