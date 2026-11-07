"""N4: REQ-0001 W0 -> W8 on screen in the data-pack app (Streamlit AppTest, no browser)."""

import html
import re
from collections import namedtuple
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from steward.auth import login

pytestmark = pytest.mark.filterwarnings("ignore")

APP = str(Path(__file__).resolve().parents[2] / "frontend" / "steward_app.py")


def as_builder(at: AppTest) -> AppTest:
    """Past the mock login (steward/auth.py) as the BI team, which sees every tab and may approve."""
    at.session_state["user"] = login("Builder12", "Admin123")
    return at
# an EXTEND; REQ-0001 itself is a CREATE (C1)
REQ1 = "Nubeqa net sales growth and forecast variance globally by country."


@pytest.fixture(autouse=True)
def fresh():
    st.cache_resource.clear()
    st.cache_data.clear()


OTHER_METRICS = {
    "Reports in catalog",
    "Certified",
    "Duplicates",
    "Retirement candidates",
    "Question coverage",
    "Trust",
    "Views (30 days)",
}  # health tab and the recommended-report block


KPI = namedtuple("KPI", "label value")
_KPI = re.compile(r'bs-kpi-label">([^<]*)</div><div class="bs-kpi-value"[^>]*>([^<]*)</div>')


def dashboard_metrics(app):
    """The dashboard's KPI cards (frontend/ui.kpi_card HTML); gap cards and st.metric tiles elsewhere are not KPIs."""
    found = []
    for m in app.markdown:
        found += [KPI(html.unescape(a), html.unescape(b)) for a, b in _KPI.findall(m.value) if "bs-gap" not in m.value]
    return found


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    app = as_builder(AppTest.from_file(APP, default_timeout=120)).run()
    return app.toggle(key="expert_mode").set_value(True).run()  # one-shot REQ-0001; novice mode interviews first


def test_req0001_shows_the_dashboard_then_approve_writes_the_spec_hash(app, tmp_path):
    assert not app.exception
    app.chat_input[0].set_value(REQ1).run()
    assert not app.exception
    assert [m.label for m in dashboard_metrics(app)] == [
        "Nubeqa net sales",
        "Nubeqa net sales growth",
        "Nubeqa forecast variance",
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


class FakeBackendLLM:
    """What get_llm returns when .env selects the backend client (Aitta / Gemini through backend/llm.py)."""

    provider = "backend"
    model = "openai/gpt-oss-120b"
    supports_embeddings = False


def test_app_loads_with_the_backend_llm_client(monkeypatch, tmp_path):
    """Regression: the sidebar crashed with KeyError 'backend' when an LLM was configured through backend/llm.py."""
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("steward.pipeline.get_llm", lambda settings: FakeBackendLLM())
    app = as_builder(AppTest.from_file(APP, default_timeout=120)).run()
    assert not app.exception
    assert any("openai/gpt-oss-120b" in c.value and "data " in c.value for c in app.sidebar.caption)


def test_pbip_download_is_offered_for_a_linted_spec_and_labelled_draft(app):
    app.chat_input[0].set_value(REQ1).run()
    assert not app.exception
    labels = [b.proto.label for b in app.get("download_button")]
    assert "Download .PBIP (draft)" in labels and "Download spec JSON" in labels
    assert any(c.value.startswith("Checked in Power BI Desktop 2.159") for c in app.caption)
    assert not any("never opened" in c.value for c in app.caption)  # true only until the first Desktop check
    assert "Download .PBIP with live refresh" not in labels  # live refresh is opt-in: nothing starts until it is ticked


def test_live_refresh_is_opt_in_and_the_service_starts_only_then(app, tmp_path, monkeypatch):
    from steward import pbip_server

    monkeypatch.setattr(pbip_server, "DEFAULT_PORT", 0)  # a free port: the tests must not fight for 8765
    app.chat_input[0].set_value(REQ1).run()
    box = next(c for c in app.checkbox if c.label.startswith("Live refresh"))
    assert not box.value and not (tmp_path / "pbip_live").exists()
    box.check().run()
    assert not app.exception
    assert "Download .PBIP with live refresh" in [b.proto.label for b in app.get("download_button")]
    assert list((tmp_path / "pbip_live").glob("*.json"))  # the approved spec was registered for the service


def test_a_lint_block_hides_the_pbip_export_and_disables_approve(app, monkeypatch):
    from steward.spec import LintResult

    blocked = [LintResult(rule_id="RULE-003", status="block", message="no owner")]
    monkeypatch.setattr("steward.lint.lint", lambda spec, catalog, *_a, **_k: blocked)
    app.chat_input[0].set_value(REQ1).run()
    assert not app.exception
    assert "Download .PBIP (draft)" not in [b.proto.label for b in app.get("download_button")]
    assert any("No .PBIP export" in c.value for c in app.caption)
    assert next(b for b in app.button if b.label == "Approve the extension").disabled
