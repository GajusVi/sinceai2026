"""T2.3 shared inbox: a handoff made in one browser reaches another (steward/inbox.py)."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from steward import Steward
from steward.auth import login
from steward.config import Settings
from steward.inbox import Inbox
from steward.worker import request_entry, same_request

pytestmark = pytest.mark.filterwarnings("ignore")
APP = str(Path(__file__).resolve().parents[2] / "frontend" / "steward_app.py")
MANAGER, BUILDER, WORKER = (
    login("Manager07", "Manage123"),
    login("Builder12", "Admin123"),
    login("Worker21", "Worker123"),
)


@pytest.fixture(scope="module")
def ruling(tmp_path_factory):
    mp = pytest.MonkeyPatch()
    mp.setenv("STEWARD_CATALOG", "datapack")
    s = Steward(
        settings=replace(
            Settings.from_env(), use_llm="off", data_dir=tmp_path_factory.mktemp("inbox"), as_of=date(2026, 11, 6)
        )
    )
    state = s.interviewer.finish_with_defaults(s.interviewer.start("Is supply safe for Plant-B?"))
    yield s.build(s.ask_intent(state.intent), state.intent, MANAGER), state.intent
    mp.undo()


def test_approval_round_trip_with_outcome_for_the_requester(tmp_path, ruling):
    result, intent = ruling
    box = Inbox(tmp_path)
    item = box.send(result, intent, True, MANAGER)
    assert box.send(result, intent, True, MANAGER) == item and len(box.open_approvals()) == 1  # not queued twice
    assert box.is_waiting("Manager07", result)

    row, again, again_intent = Inbox(tmp_path).take(item, BUILDER.label)  # a new object = another session
    assert again.model_dump() == result.model_dump() and again_intent == intent
    assert box.open_approvals() == [] and box.take(item, BUILDER.label) is None  # nobody else can open it now

    box.decide(item, "sent_back", BUILDER.label, reason="Use the Plant-B ops report")
    notices = box.pop_notices("Manager07")
    assert len(notices) == 1 and "sent back" in notices[0] and "Plant-B ops report" in notices[0]
    assert box.pop_notices("Manager07") == []  # shown once


def test_release_puts_an_undecided_review_back(tmp_path, ruling):
    result, intent = ruling
    box = Inbox(tmp_path)
    item = box.send(result, intent, True, MANAGER)
    box.take(item, BUILDER.label)
    box.release(item)
    assert [a["id"] for a in box.open_approvals()] == [item]


def test_floor_requests_merge_grant_and_notify_everyone(tmp_path):
    box = Inbox(tmp_path)
    first = request_entry(WORKER, "access", "Weeks of stock", department="Quality", cadence="Weekly")
    row, joined = box.add_floor(first, same_request)
    assert not joined and row["id"]
    other = {**first, "username": "Worker22", "who": "Worker22"}
    row2, joined2 = box.add_floor(other, same_request)
    assert joined2 and row2["id"] == row["id"] and row2["also"] == ["Worker22"]

    box.decide_floor(row["id"], "granted", BUILDER.label)
    assert box.grants("Worker21") == ["Quality"] and box.floor("open") == []
    assert "granted" in box.pop_notices("Worker21")[0] and "granted" in box.pop_notices("Worker22")[0]


def test_two_browsers_manager_sends_builder_sees_it(monkeypatch, tmp_path):
    """Two AppTest sessions = two browsers: no shared st.session_state, only the data dir."""
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    st.cache_resource.clear()
    st.cache_data.clear()

    manager = AppTest.from_file(APP, default_timeout=120)
    manager.session_state["user"] = MANAGER
    manager.run()
    manager.chat_input[0].set_value("Is supply safe for Plant-B?").run()
    next(b for b in manager.button if b.label == "Use recommended").click().run()
    next(b for b in manager.button if b.label == "Send to the BI team for approval").click().run()
    assert not manager.exception and len(Inbox(tmp_path).open_approvals()) == 1

    builder = AppTest.from_file(APP, default_timeout=120)
    builder.session_state["user"] = BUILDER
    builder.run()
    assert not builder.exception
    assert any("Waiting for your approval (1)" in m.value for m in builder.markdown)
    next(b for b in builder.button if b.label == "Review").click().run()
    next(t for t in builder.text_input if t.label == "Reason, if you send it back").set_value("Use the ops report")
    next(b for b in builder.button if b.label == "Send back").click().run()
    assert not builder.exception and Inbox(tmp_path).open_approvals() == []

    manager.run()  # the manager's next page load shows the outcome
    assert any("sent back by Builder12" in i.value and "Use the ops report" in i.value for i in manager.info)


def test_start_it_runs_on_the_governed_ids_not_on_text(monkeypatch, tmp_path):
    """C9: a floor request carries its metric ids; the builder's Start it builds from them, scoped to the plant."""
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    st.cache_resource.clear()
    st.cache_data.clear()
    Inbox(tmp_path).add_floor(request_entry(WORKER, "report", "On-Time In-Full", metric_ids=["on_time_in_full"]),
                              same_request)
    builder = AppTest.from_file(APP, default_timeout=120)
    builder.session_state["user"] = BUILDER
    builder.run()
    next(b for b in builder.button if b.label == "Start it").click().run()
    assert not builder.exception
    intent = builder.session_state["result_intent"]
    assert intent.metric_ids == ["on_time_in_full"] and intent.sites == ["Plant-A"]
    assert builder.session_state["result"].spec is not None and Inbox(tmp_path).floor("open") == []
    assert "picked up" in Inbox(tmp_path).pop_notices("Worker21")[0]


def test_reviews_left_open_by_a_builder_go_back_to_the_queue(tmp_path, ruling):
    """The desktop app's Log out is a link: a review left open is released on that builder's next page load."""
    result, intent = ruling
    box = Inbox(tmp_path)
    item = box.send(result, intent, True, MANAGER)
    box.take(item, BUILDER.label)
    box.release_reviews_of("Someone else")
    assert box.open_approvals() == []
    box.release_reviews_of(BUILDER.label)
    assert [a["id"] for a in box.open_approvals()] == [item]
