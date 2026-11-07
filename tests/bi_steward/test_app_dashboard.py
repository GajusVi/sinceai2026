"""N4: REQ-0001 W0 -> W8 on screen in the data-pack app (Streamlit AppTest, no browser)."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

pytestmark = pytest.mark.filterwarnings("ignore")

APP = str(Path(__file__).resolve().parents[2] / "frontend" / "steward_app.py")
REQ1 = "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country."


@pytest.fixture(autouse=True)
def fresh():
    st.cache_resource.clear()
    st.cache_data.clear()


OTHER_METRICS = {"Reports in catalog", "Certified", "Duplicates", "Retirement candidates",
                 "Question coverage", "Trust", "Views (30 days)"}  # health tab and the recommended-report block


def dashboard_metrics(app):
    """The health tab and the decision block render their own metrics; the dashboard's are the others."""
    return [m for m in app.metric if m.label not in OTHER_METRICS]


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    return AppTest.from_file(APP, default_timeout=120).run()


def test_req0001_shows_the_dashboard_then_approve_writes_the_spec_hash(app, tmp_path):
    assert not app.exception
    app.chat_input[0].set_value(REQ1).run()
    assert not app.exception
    assert [m.label for m in dashboard_metrics(app)] == [
        "Nubeqa net sales", "Nubeqa net sales growth", "Nubeqa forecast variance", "Nubeqa market access coverage",
    ]
    assert any(c.value.startswith("v2 (extend)") or "Source model" in c.value for c in app.caption)
    assert {s.label for s in app.selectbox} >= {"Product", "Market"}

    approve = next(b for b in app.button if b.label == "Approve the extension")
    assert not approve.disabled
    approve.click().run()
    assert not app.exception
    journal = (tmp_path / "journal.jsonl").read_text(encoding="utf-8")
    assert '"spec_hash":"' in journal and '"spec_hash":""' not in journal
    assert list((tmp_path / "specs").glob("*.json"))


def test_a_filter_changes_the_numbers(app):
    app.chat_input[0].set_value(REQ1).run()
    before = [m.value for m in dashboard_metrics(app)]
    market = next(s for s in app.selectbox if s.label == "Market")
    market.select("DE").run()
    assert not app.exception
    assert [m.value for m in dashboard_metrics(app)] != before


def test_clarify_shows_no_dashboard(app):
    app.chat_input[0].set_value("Show me something interesting").run()
    assert not app.exception and not dashboard_metrics(app)
