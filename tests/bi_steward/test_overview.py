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
