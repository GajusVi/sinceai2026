from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest


@pytest.fixture(autouse=True)
def fresh_steward():
    """The app caches Steward with st.cache_resource; each test sets its own env, so start clean."""
    st.cache_resource.clear()
    st.cache_data.clear()


APP = str(Path(__file__).resolve().parents[2] / "frontend" / "steward_app.py")


def test_chat_question_renders_without_exception(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    at.chat_input[0].set_value("Net revenue by region for Q3").run()
    assert not at.exception
    assert len(at.session_state["messages"]) == 2


def test_reset_demo_twice(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    (tmp_path / "journal.jsonl").write_text("")
    at = AppTest.from_file(APP, default_timeout=60).run()
    for _ in range(2):
        next(b for b in at.sidebar.button if b.label == "Reset demo").click().run()
        assert not at.exception
    assert not (tmp_path / "journal.jsonl").exists()


def test_orphan_rescue_on_datapack(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    assert any("AST-0091" in s.value for s in at.subheader)
    assert any("inactive" in m.value for m in at.markdown)
    # reason is required, then the proposal lands in the journal
    next(b for b in at.button if b.label == "Retire candidate").click().run()
    assert any("reason" in e.value.lower() for e in at.error)
    at.text_input(key="orphan_reason_AST-0091").set_value("No users, owner left").run()
    next(b for b in at.button if b.label == "Retire candidate").click().run()
    assert not at.exception
    assert "PROPOSAL" in (tmp_path / "journal.jsonl").read_text()


def test_orphan_rescue_on_sample_catalog(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STEWARD_CATALOG", raising=False)
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("make bayer" in i.value for i in at.info)
