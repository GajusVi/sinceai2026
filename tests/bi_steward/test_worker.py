"""Worker fast path (steward/worker.py, frontend/worker_view.py): reuse only, own plant only, no interview."""

from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from steward import Steward, semantic
from steward.auth import login
from steward.models import Verdict
from steward.worker import menu, open_item, other_plant, refusal, reuse_only, sites_named, suggest, words_to_metrics

APP = str(Path(__file__).resolve().parents[2] / "frontend" / "steward_app.py")


@pytest.fixture(scope="module")
def env():
    mp = pytest.MonkeyPatch()
    mp.setenv("STEWARD_USE_LLM", "off")
    mp.setenv("STEWARD_CATALOG", "datapack")
    frames = semantic.load_frames()
    supply = frames["fact_supply"].merge(frames["dim_product"][["product_id", "product_name"]], on="product_id")
    yield Steward(), list(supply[["product_name", "market_id", "supply_source"]].itertuples(index=False, name=None))
    mp.undo()


def test_reuse_only_shows_an_existing_report_on_the_workers_plant(env):
    steward, supply = env
    worker = login("Worker21", "Worker123")
    answer = reuse_only(steward, worker, ["inventory_coverage"], "stock", supply)
    assert answer.result.decision.verdict == Verdict.REUSE  # never a new build
    assert answer.result.spec.change_type == "reuse" and answer.result.spec.filters["site"] == "Plant-A"
    assert answer.result.decision.best.artifact.id in steward.catalog.artifacts and not answer.missing


def test_missing_numbers_are_listed_not_built(env):
    steward, supply = env
    asked = ["on_time_in_full", "inventory_coverage", "demand_forecast_accuracy"]
    answer = reuse_only(steward, login("Worker21", "Worker123"), asked, "supply", supply)
    assert answer.covered and answer.missing and set(answer.covered) | set(answer.missing) == set(asked)


def test_other_plants_are_refused_for_workers_and_management():
    worker, manager = login("Worker21", "Worker123"), login("Manager07", "Manage123")
    assert other_plant(worker, ["Plant-B"]) == "Plant-B" and "manager" in refusal(worker, "Plant-B")
    assert other_plant(manager, ["Plant-B"]) == "" and other_plant(manager, ["Plant-C"]) == "Plant-C"
    assert other_plant(login("Builder12", "Admin123"), ["Plant-C"]) == ""


def test_floor_words():
    assert words_to_metrics("how many weeks of stock do we have?")[0] == ["inventory_coverage"]
    assert words_to_metrics("downtime on line 3") == ([], "line downtime")
    assert words_to_metrics("did we ship more than last month?")[0] == ["units_shipped"]
    assert words_to_metrics("anything related to this") == ([], "")  # "late" is not inside "related"


def test_worker_screen_has_buttons_not_a_chat_box(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    st.cache_resource.clear()
    st.cache_data.clear()
    at = AppTest.from_file(APP, default_timeout=180)
    at.session_state["user"] = login("Worker21", "Worker123")
    at.run()
    assert not at.exception and not at.chat_input and [t.label for t in at.tabs] == ["Ask", "Catalog"]
    labels = [b.label for b in at.button]
    assert labels[0] == "Chat" and "Other department" in labels and "Is supply safe at my plant?" in labels
    next(b for b in at.button if b.label == "Weeks of stock on hand").click().run()
    assert not at.exception and any(c.value.startswith("From the existing report") for c in at.caption)


class FakeLLM:
    def __init__(self, raw):
        self.raw = raw

    def generate_json(self, prompt):
        assert "kpi:inventory_coverage" in prompt  # the menu is in the prompt
        return self.raw


def test_plan_my_day_suggests_kpis_without_building(env):
    steward, supply = env
    worker = login("Worker21", "Worker123")
    offline = suggest(steward, worker, "how do I plan my day", supply)  # no LLM: the department's usual numbers
    assert offline.items and all(i.id.startswith("kpi:") for i in offline.items) and not offline.by_ai
    first = open_item(steward, worker, offline.items[0].id, supply)
    assert first.result is None or first.result.decision.verdict == Verdict.REUSE


def test_ai_picks_are_validated_against_the_menu(env, monkeypatch):
    steward, supply = env
    worker = login("Worker21", "Worker123")
    raw = {"reply": "Start with stock.", "picks": [{"id": "kpi:inventory_coverage", "why": "stock first"},
                                                  {"id": "kpi:made_up", "why": "x"}, {"id": "dashboard:new"}]}
    monkeypatch.setattr(steward, "llm", FakeLLM(raw))
    answer = suggest(steward, worker, "how do I plan my day", supply)
    assert answer.by_ai and [i.id for i in answer.items] == ["kpi:inventory_coverage"]  # invented ids dropped
    report = next(k for k in menu(steward, worker, supply) if k.startswith("report:"))
    assert open_item(steward, worker, report, supply).result.decision.best.artifact.id == report.split(":")[1]


def test_plants_named_in_text():
    assert sites_named("how is plant b doing") == ["Plant-B"] and sites_named("the CMO") == ["External-CMO"]


def test_padding_picks_are_dropped_and_commercial_kpis_never_offered(env, monkeypatch):
    steward, supply = env
    worker = login("Worker21", "Worker123")
    options = menu(steward, worker, supply)
    assert "kpi:net_sales" not in options and "kpi:inventory_coverage" in options  # the floor gets operations KPIs
    raw = {"reply": "Check stock.", "picks": [{"id": "kpi:inventory_coverage"}, {"id": "kpi:units_shipped"}]}
    monkeypatch.setattr(steward, "llm", FakeLLM(raw))
    stock = suggest(steward, worker, "Which product is running low on stock?", supply)
    assert [i.id for i in stock.items] == ["kpi:inventory_coverage"]  # units shipped was padding
    broad = suggest(steward, worker, "What do I do today", supply)
    assert len(broad.items) == 2  # a broad question keeps the AI's picks
    monkeypatch.setattr(steward, "llm", None)
    late = suggest(steward, worker, "Are we late on any deliveries this month?", supply)
    assert [i.id for i in late.items] == ["kpi:on_time_in_full"]  # offline: no padding either
