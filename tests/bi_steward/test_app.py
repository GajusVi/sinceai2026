from pathlib import Path

from streamlit.testing.v1 import AppTest

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
