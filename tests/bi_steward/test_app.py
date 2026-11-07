from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from steward.auth import login


@pytest.fixture(autouse=True)
def fresh_steward():
    """The app caches Steward with st.cache_resource; each test sets its own env, so start clean."""
    st.cache_resource.clear()
    st.cache_data.clear()


APP = str(Path(__file__).resolve().parents[2] / "frontend" / "steward_app.py")


def as_builder(at: AppTest) -> AppTest:
    """Past the mock login (steward/auth.py) as the BI team, which sees every tab and may approve."""
    at.session_state["user"] = login("Builder12", "Admin123")
    return at


def test_chat_question_renders_without_exception(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    at = as_builder(AppTest.from_file(APP, default_timeout=60)).run()
    assert not at.exception
    at.chat_input[0].set_value("Net revenue by region for Q3").run()
    assert not at.exception
    assert len(at.session_state["messages"]) == 2


def test_reset_demo_twice(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    (tmp_path / "journal.jsonl").write_text("")
    at = as_builder(AppTest.from_file(APP, default_timeout=60)).run()
    for _ in range(2):
        next(b for b in at.sidebar.button if b.label == "Reset demo").click().run()
        assert not at.exception
    assert not (tmp_path / "journal.jsonl").exists()


def test_orphan_rescue_on_datapack(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    at = as_builder(AppTest.from_file(APP, default_timeout=120)).run()
    assert not at.exception
    assert any("AST-0091" in s.value for s in at.subheader)
    assert any("inactive" in m.value for m in at.markdown)
    # reason is required, then the proposal lands in the journal
    next(b for b in at.button if b.label == "Retire candidate").click().run()
    assert any("reason" in e.value.lower() for e in at.error)
    at.text_input(key="orphan_reason_AST-0091").set_value("No users, owner left").run()
    next(b for b in at.button if b.label == "Retire candidate").click().run()
    assert not at.exception
    journal = (tmp_path / "journal.jsonl").read_text()
    assert "PROPOSAL" in journal and '"action":"proposed"' in journal


def test_default_catalog_is_the_data_pack(monkeypatch, tmp_path):
    """T3.7: no STEWARD_CATALOG set still opens the data pack (the invented sample catalog is gone)."""
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STEWARD_CATALOG", raising=False)
    at = as_builder(AppTest.from_file(APP, default_timeout=180)).run()
    assert not at.exception
    assert not any("make bayer" in i.value for i in at.info)


def _novice_app(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    return as_builder(AppTest.from_file(APP, default_timeout=180)).run()


def _click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception


def test_novice_chat_one_click_answers_then_dashboard_first(monkeypatch, tmp_path):
    at = _novice_app(monkeypatch, tmp_path)
    at.chat_input[0].set_value("How efficiently is this plant running?").run()
    assert not at.exception and at.session_state["messages"][-1]["content"] == "Which site do you mean?"
    _click(at, "Plant-B")
    _click(at, "Yes, use these")
    _click(at, "Board update")
    assert at.session_state["messages"][-2]["content"].startswith("Got it: Plant-B")
    assert "Nothing like this exists yet" in at.session_state["messages"][-1]["content"]  # plain words, no verdict
    assert at.session_state["result"].spec.filters["site"] == "Plant-B"
    assert any("Plant-B: how well a site is running" in m.value and "bs-verdict" in m.value for m in at.markdown)
    assert not any("Lint gate" in m.value for m in at.markdown)  # governance only behind the details toggle


def test_skip_uses_the_recommended_setup(monkeypatch, tmp_path):
    at = _novice_app(monkeypatch, tmp_path)
    at.chat_input[0].set_value("How efficiently is this plant running?").run()
    _click(at, "Plant-C")
    _click(at, "Use recommended")
    assert at.session_state["result"].spec.filters["site"] == "Plant-C"
