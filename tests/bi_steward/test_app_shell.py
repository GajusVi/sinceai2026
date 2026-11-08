"""T2.6 desktop app: the signed login handover (steward/apptoken.py) and the workspace mechanics in app mode."""
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from steward import apptoken
from steward.auth import account

pytestmark = pytest.mark.filterwarnings("ignore")
APP = str(Path(__file__).resolve().parents[2] / "frontend" / "steward_app.py")


def test_token_signs_one_user_for_a_short_time():
    t = apptoken.sign("Manager07", "s3cret", now=1000)
    assert apptoken.verify("Manager07", t, "s3cret", now=1060)
    assert not apptoken.verify("Builder12", t, "s3cret", now=1060)  # another user
    assert not apptoken.verify("Manager07", t, "other", now=1060)  # another app run
    assert not apptoken.verify("Manager07", t, "s3cret", now=1000 + apptoken.MAX_AGE_S + 1)  # too old
    assert not apptoken.verify("Manager07", "garbage", "s3cret") and not apptoken.verify("Manager07", t, "")
    assert account("manager07").username == "Manager07" and account("nobody") is None


@pytest.fixture
def app_mode(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    monkeypatch.setenv(apptoken.ENV_SECRET, "test-secret")
    monkeypatch.setenv(apptoken.ENV_LOGIN_URL, "http://127.0.0.1:1/app/shell/login.html")
    st.cache_resource.clear()
    st.cache_data.clear()


def test_signed_handover_opens_the_workspace(app_mode):
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params["u"] = "Manager07"
    at.query_params["t"] = apptoken.sign("Manager07", "test-secret")
    at.run()
    assert not at.exception and at.session_state["user"].username == "Manager07"
    assert at.radio(key="nav").options == ["Ask", "Journal", "Catalog"]  # the rail, by role
    assert not [t for t in at.text_input if t.label in ("Username", "Password")]  # the native window signs in


def test_a_forged_token_stays_signed_out(app_mode):
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params["u"] = "Builder12"
    at.query_params["t"] = apptoken.sign("Builder12", "wrong-secret")
    at.run()
    assert not at.exception and "user" not in at.session_state
    assert any("Signed out" in m.value for m in at.markdown)
