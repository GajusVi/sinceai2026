"""OVERVIEW dashboards (Donatas, 8 Nov): lint FOCUS/DATA for the archetype; more tests land with specbuild/render."""
from steward import lint
from steward.spec import DashboardSpec, Measure, Page, Visual


def _spec(visuals, measures=None, archetype="OVERVIEW"):
    measures = measures or [Measure(name=f"M{i}", kpi_id=f"KPI-{i:03d}") for i in range(1, 9)]
    spec = DashboardSpec(name="Plant-B", measures=measures, pages=[Page(name="Overview", visuals=visuals)])
    return spec.model_copy(update={"archetype": archetype})  # the field lands in spec.py; getattr reads it either way


def _strip(n):
    return Visual(type="kpi_strip", title="Today", measures=[f"M{i}" for i in range(1, n + 1)])


def _charts(n):
    return [Visual(type="line", title=f"C{i}", measures=["M1"]) for i in range(n)]


def test_overview_strip_counts_as_one_visual():
    result = lint._focus(_spec([_strip(8), *_charts(6)]), None)
    assert result.status == "pass"  # 8 tiles + 6 charts: inside the overview caps, though 14 > 7 visuals and 8 > 4 cards


def test_overview_caps_warn():
    assert lint._focus(_spec([_strip(9)]), None).status == "warn"
    assert lint._focus(_spec([_strip(4), *_charts(7)]), None).status == "warn"
    assert lint._focus(_spec([_strip(2), _strip(2)]), None).status == "warn"


def test_template_focus_unchanged_without_archetype():
    cards = [Visual(type="card", title=f"K{i}", measures=["M1"]) for i in range(5)]
    assert lint._focus(_spec(cards, archetype=""), None).status == "warn"  # 5 cards > 4, as before


def test_gap_allowed_as_tile_never_in_a_chart():
    measures = [Measure(name="Gap", kpi_id="KPI-034", feasible=False, gap_reason="no source data", expression="")]
    ok = _spec([Visual(type="kpi_strip", title="Today", measures=["Gap"])], measures)
    assert lint._data(ok, None).status == "pass"
    bad = _spec([Visual(type="bullet", title="Gap vs target", measures=["Gap"])], measures)
    assert lint._data(bad, None).status == "block"


# -- builder: archetype choice, the OVERVIEW template, the switch, old hashes ------------------------------------------
import pytest  # noqa: E402

from steward import specbuild  # noqa: E402
from steward.auth import login  # noqa: E402
from steward.layout import validate_overview  # noqa: E402


@pytest.fixture(scope="module")
def steward(tmp_path_factory):
    from dataclasses import replace
    from datetime import date

    from steward import Steward
    from steward.config import Settings

    settings = replace(Settings.from_env(), use_llm="off", data_dir=tmp_path_factory.mktemp("ov"), as_of=date(2026, 11, 6))
    return Steward(settings=settings)


def _build(steward, text, account):
    state = steward.interviewer.start(text)
    intent = steward.interviewer.finish_with_defaults(state).intent
    return steward.build(steward.ask_intent(intent), intent, login(*account)).spec


MANAGER, WORKER, BUILDER = ("Manager07", "Manage123"), ("Worker21", "Worker123"), ("Builder12", "Admin123")
REQ_0001 = "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country."


def test_plant_overview_for_management_is_a_valid_grid(steward):
    spec = _build(steward, "How is Plant-B doing?", MANAGER)
    assert spec.archetype == "OVERVIEW" and spec.provenance["layout_source"] == "overview"
    page = spec.pages[0]
    assert page.visuals[0].type == "kpi_strip" and page.visuals[-1].type == "table"
    assert validate_overview(page, {m.name for m in spec.measures}, {m.name for m in spec.measures if not m.feasible}) == []
    assert all(r.status != "block" for r in spec.lint)


def test_workers_and_req_0001_keep_the_template(steward):
    assert getattr(_build(steward, "How is Plant-B doing?", WORKER), "archetype", "") == ""
    assert getattr(_build(steward, REQ_0001, BUILDER), "archetype", "") == ""


def test_old_spec_hashes_are_unchanged(steward):
    """Pinned before OVERVIEW existed (8 Nov 01:50): templates hash exactly as before."""
    assert _build(steward, REQ_0001, BUILDER).provenance["spec_hash"] == "8689405319e3aeb7"
    assert _build(steward, "How is Plant-B doing?", WORKER).provenance["spec_hash"] == "dc45735e316585d3"
    assert _build(steward, "Xarelto net sales in Germany", MANAGER).provenance["spec_hash"] == "7e0bb4672d7eebfd"


def test_one_switch_turns_overview_off(steward, monkeypatch):
    monkeypatch.setattr(specbuild, "OVERVIEW_ON", False)
    assert getattr(_build(steward, "How is Plant-B doing?", MANAGER), "archetype", "") == ""


def test_validator_rejects_bad_rows_and_gaps_in_charts():
    def at(v, row, span):
        return v.model_copy(update={"row": row, "span": span})

    strip = at(_strip(2), 1, 12)
    bad_row = Page(name="x", visuals=[strip, at(Visual(type="line", title="a", measures=["M1"]), 2, 6)])
    assert any("sum to 6" in p for p in validate_overview(bad_row, {"M1", "M2"}, set()))
    gap_chart = Page(name="x", visuals=[strip, at(Visual(type="bullet", title="g", measures=["M2"]), 2, 12)])
    assert any("labelled tile" in p for p in validate_overview(gap_chart, {"M1", "M2"}, {"M2"}))
