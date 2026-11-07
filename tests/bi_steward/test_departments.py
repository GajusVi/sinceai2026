"""Department -> KPI map: AI drafts, code validates, builder approves, workers read only the approved map."""

import pytest

from steward import Steward, departments
from steward.auth import login
from steward.worker import DEPARTMENTS, department_kpis, prompts_for


class FakeLLM:
    def __init__(self, raw):
        self.raw = raw

    def generate_json(self, prompt):
        assert "KPI-020" in prompt and "Warehouse Ops" in prompt
        return self.raw


@pytest.fixture
def steward(monkeypatch, tmp_path):
    monkeypatch.setenv("STEWARD_USE_LLM", "off")
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    monkeypatch.setenv("STEWARD_DATA_DIR", str(tmp_path))
    return Steward()


def test_ai_draft_keeps_only_real_ids_and_departments(steward):
    raw = {"map": {"Warehouse Ops": [{"id": "KPI-020", "why": "late deliveries"}, {"id": "KPI-999"},
                                     {"id": "inventory_coverage", "why": "stock"}],
                   "Made-up Dept": [{"id": "KPI-001"}]},
           "missing": {"Equipment Ops": ["line downtime"]}}
    draft = departments.propose(FakeLLM(raw), steward.settings.prompts_dir, steward.catalog, DEPARTMENTS)
    assert draft["source"] == "ai" and draft["map"]["Warehouse Ops"] == ["on_time_in_full", "inventory_coverage"]
    assert "Made-up Dept" not in draft["map"] and draft["missing"]["Equipment Ops"] == ["line downtime"]


def test_no_model_gives_the_defaults(steward):
    draft = departments.propose(None, steward.settings.prompts_dir, steward.catalog, DEPARTMENTS)
    assert draft["source"] == "default" and draft["map"] == departments.defaults()


def test_workers_read_only_the_approved_map(steward):
    worker = login("Worker21", "Worker123")  # Warehouse Ops
    assert department_kpis(steward, "Warehouse Ops") == departments.defaults()["Warehouse Ops"]
    departments.save_draft(steward.data_dir, {"map": {"Warehouse Ops": ["units_shipped"]}, "source": "ai"}, "b")
    assert department_kpis(steward, "Warehouse Ops") != ["units_shipped"]  # a draft changes nothing on the floor
    departments.approve(steward.data_dir, {"Warehouse Ops": ["units_shipped", "not_a_metric"]}, "Builder12",
                        steward.catalog)
    assert department_kpis(steward, worker.department) == ["units_shipped"]  # invalid id dropped at approval
    assert [p.label for p in prompts_for(steward, "Warehouse Ops")] == ["Units Shipped"]
    assert departments.state(steward.data_dir)["log"][-1]["who"] == "Builder12"
