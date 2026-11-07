"""N4: the renderer. Deterministic; a gap measure is never a number; values equal semantic.compute."""
from pathlib import Path

import pytest

from steward import semantic
from steward.render import render
from steward.spec import DashboardSpec, Visual

pytestmark = pytest.mark.filterwarnings("ignore")

FIXTURE = Path(__file__).parent / "fixtures" / "spec_req0001.json"


@pytest.fixture(scope="module")
def frames():
    return semantic.load_frames()


@pytest.fixture(scope="module")
def spec():
    return DashboardSpec.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_renders_cards_line_bar_table_and_footer(spec, frames):
    d = render(spec, frames)
    assert [c.kpi_id for c in d.cards] == ["KPI-001", "KPI-004", "KPI-042", "KPI-027"] and not d.gaps
    assert [t for t, _ in d.figures] == ["Nubeqa net sales vs forecast, by month", "Nubeqa net sales, by country"]
    line = d.figures[0][1]
    assert [t.name for t in line.data] == ["Net Sales", "Forecast"] and len(line.data[0].x) == 10
    assert len(d.tables) == 1 and list(d.tables[0][1].columns) == ["Country", "Variance (EUR M)", "Off forecast (%)"]
    assert (d.tables[0][1]["Off forecast (%)"].abs() > 10).all()
    labels = dict(d.footer)
    assert "KPI-001 Net Sales (canonical)" in labels["KPIs"] and "SM-069" in labels["Source model"]
    assert "OWN-004" in labels["Owner"] and "Synthetic" in labels["Data"]
    assert labels["Version"].startswith("v2 (extend)")


def test_card_values_are_the_governed_numbers(spec, frames):
    d = render(spec, frames)
    cards = {c.kpi_id: c for c in d.cards}
    filters = {"product": "Nubeqa"}
    total = float(semantic.compute(semantic.measure("KPI-001"), frames, filters)["value"].iloc[0])
    fc = float(semantic.forecast(frames, filters)["value"].iloc[0])
    assert cards["KPI-001"].value == semantic.display("KPI-001", total)
    assert cards["KPI-001"].comparison == f"{(total - fc) / fc * 100:+.1f}% vs forecast"
    assert cards["KPI-004"].value.endswith("%") and "pp vs last month" in cards["KPI-004"].comparison
    assert "of forecast" in cards["KPI-042"].comparison


def test_filters_override_the_spec_and_change_the_numbers(spec, frames):
    nub = render(spec, frames)
    de = render(spec, frames, {"market": "DE"})
    assert nub.cards[0].value != de.cards[0].value and de.filters["market"] == "DE"
    later = render(spec, frames, {"month_from": "2026-09"})
    assert len(later.figures[0][1].data[0].x) == 2
    assert later.cards[0].value != nub.cards[0].value


def test_a_gap_measure_is_a_gap_card_and_never_a_number(spec, frames):
    gap_spec = spec.model_copy(deep=True)
    gap_spec.measures.append(semantic.measure("KPI-034"))
    gap_card = Visual(type="card", title="Gross-to-net", measures=["Gross-to-Net Rate"])
    gap_spec.pages[0].visuals.insert(0, gap_card)
    d = render(gap_spec, frames)
    assert [g.kpi_id for g in d.gaps] == ["KPI-034"] and "no governed model" in d.gaps[0].reason
    assert "KPI-034" not in {c.kpi_id for c in d.cards}
    assert "no source data" in dict(d.footer)["KPIs"]


def test_render_is_deterministic(spec, frames):
    a, b = render(spec, frames), render(spec, frames)
    assert [c.value for c in a.cards] == [c.value for c in b.cards]
    assert a.figures[0][1].to_json() == b.figures[0][1].to_json()
    assert a.tables[0][1].equals(b.tables[0][1])


def test_missing_owner_is_said_in_the_footer(spec, frames):
    nobody = spec.model_copy(update={"owner_id": ""})
    assert "must assign" in dict(render(nobody, frames).footer)["Owner"]
