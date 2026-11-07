"""Structure checks for the .PBIP export. The layout copies projects saved by Power BI Desktop 2.159 (templates/pbip/).
Whether Desktop opens the export is checked by hand (submission/pbip_open.png), not here."""

import base64
import json
import re
import zipfile
import zlib
from pathlib import Path

import pandas as pd
import pytest

from steward.pbip import _format_string, _q, _safe_name, build_files, export_pbip
from steward.semantic import all_measures, load_frames
from steward.spec import DashboardSpec, Measure, Page, Relationship, Visual

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "templates" / "pbip" / "one_of_each" / "one_of_each.Report"
NAME = "Nubeqa_net_sales_draft"
SM, RP = f"{NAME}.SemanticModel", f"{NAME}.Report"


@pytest.fixture
def frames():
    return {
        "fact_pmm": pd.DataFrame(
            {
                "product_id": ["P-NUB", "P-NUB"],
                "market_id": ["DE", "FR"],
                "month": pd.to_datetime(["2026-01-01", "2026-02-01"]),
                "net_sales": [1.5, None],
                "units": [3, 4],
            }
        ),
        "dim_product": pd.DataFrame({"product_id": ["P-NUB"], "product_name": ["Nubeqa"]}),
    }


@pytest.fixture
def spec():
    return DashboardSpec(
        name="Nubeqa net sales (draft)",
        entities=["fact_pmm", "dim_product"],
        columns={
            "fact_pmm": ["product_id", "market_id", "month", "net_sales", "units"],
            "dim_product": ["product_id", "product_name"],
        },
        relationships=[Relationship(from_entity="fact_pmm", to_entity="dim_product", key="product_id")],
        measures=[Measure(name="Net Sales", kpi_id="KPI-001", expression="SUM(fact_pmm[net_sales])", format="#,##0.0")],
        pages=[
            Page(
                name="What needs attention",
                visuals=[
                    Visual(type="card", title="Net sales", measures=["Net Sales"]),
                    Visual(type="bar", title="By product", measures=["Net Sales"], dimension="product"),
                    Visual(type="table", title="Detail", measures=["Net Sales"], dimension="product"),
                ],
            )
        ],
    )


def _visuals(files: dict[str, str]) -> list[dict]:
    return [json.loads(t) for p, t in sorted(files.items()) if p.endswith("/visual.json")]


def test_names_quoting_and_formats():
    assert _safe_name("Nubeqa net sales (draft)") == NAME
    assert len(_safe_name("x" * 200)) <= 40 and _safe_name("???") == "dashboard"
    assert _q("fact_pmm") == "fact_pmm" and _q("Net Sales") == "'Net Sales'" and _q("it's") == "'it''s'"
    assert _format_string("0.0%") == "0.0%" and _format_string("EUR M") == '#,0.0" EUR M"'
    assert _format_string("0.0 weeks") == '0.0" weeks"'


def test_folder_layout_matches_what_desktop_saved(spec, frames):
    files = build_files(spec, frames)
    for path in (
        f"{NAME}.pbip",
        f"{SM}/definition.pbism",
        f"{SM}/.platform",
        f"{SM}/definition/database.tmdl",
        f"{SM}/definition/model.tmdl",
        f"{SM}/definition/relationships.tmdl",
        f"{SM}/definition/cultures/en-US.tmdl",
        f"{SM}/definition/tables/fact_pmm.tmdl",
        f"{SM}/definition/tables/dim_product.tmdl",
        f"{RP}/definition.pbir",
        f"{RP}/.platform",
        f"{RP}/definition/report.json",
        f"{RP}/definition/version.json",
        f"{RP}/definition/pages/pages.json",
        "README.txt",
        "spec.json",
    ):
        assert path in files, path
    assert json.loads(files[f"{NAME}.pbip"])["artifacts"] == [{"report": {"path": f"{NAME}.Report"}}]
    assert json.loads(files[f"{SM}/definition.pbism"])["version"] == "4.2"
    assert "compatibilityLevel: 1606" in files[f"{SM}/definition/database.tmdl"]
    assert json.loads(files[f"{RP}/definition.pbir"])["datasetReference"]["byPath"]["path"] == f"../{SM}"
    assert not [p for p in files if p.startswith("data/")]  # data is embedded: nothing to configure
    assert all("DataFolder" not in t for t in files.values())


def test_report_json_and_theme_are_copied_from_the_desktop_template(spec, frames):
    files = build_files(spec, frames)
    assert json.loads(files[f"{RP}/definition/report.json"]) == json.loads(
        (TEMPLATE / "definition" / "report.json").read_text(encoding="utf-8")
    )
    assert files[f"{RP}/definition/version.json"].strip() == (TEMPLATE / "definition/version.json").read_text(encoding="utf-8").strip()
    assert f"{RP}/StaticResources/SharedResources/BaseThemes/Fluent2-CY26SU10.json" in files


def test_tables_have_measures_columns_and_embedded_data(spec, frames):
    files = build_files(spec, frames)
    fact = files[f"{SM}/definition/tables/fact_pmm.tmdl"]
    assert fact.startswith("table fact_pmm\n")
    assert "\tmeasure 'Net Sales' = SUM(fact_pmm[net_sales])\n\t\tformatString: #,##0.0" in fact
    assert "\tcolumn net_sales\n\t\tdataType: double" in fact and "\t\tsourceColumn: net_sales" in fact
    assert "dataType: int64" in fact and "dataType: dateTime" in fact and "dataType: string" in fact
    assert "measure" not in files[f"{SM}/definition/tables/dim_product.tmdl"]  # measures only on the fact table
    assert "ref table fact_pmm\nref table dim_product\n" in files[f"{SM}/definition/model.tmdl"]
    assert "\trelationship" not in files[f"{SM}/definition/relationships.tmdl"]
    rel = files[f"{SM}/definition/relationships.tmdl"]
    assert "\tfromColumn: fact_pmm.product_id\n\ttoColumn: dim_product.product_id" in rel
    for path, text in files.items():  # TMDL indents with tabs, never spaces
        if path.endswith(".tmdl"):
            assert not [ln for ln in text.splitlines() if ln.startswith(" ")], path


def test_embedded_rows_round_trip_exactly(spec, frames):
    fact = build_files(spec, frames)[f"{SM}/definition/tables/fact_pmm.tmdl"]
    encoded = re.search(r'Binary.FromText\("([^"]+)"', fact).group(1)
    rows = json.loads(zlib.decompress(base64.b64decode(encoded), -15))  # raw deflate, as Compression.Deflate reads it
    assert rows == [["P-NUB", "DE", "2026-01-01", 1.5, 3], ["P-NUB", "FR", "2026-02-01", None, 4]]
    assert 'type date' in fact and 'Int64.Type' in fact and "Table.FromRows" in fact


def test_visuals_map_to_pbir_types_and_bind_to_measures(spec, frames):
    visuals = {v["visual"]["visualType"]: v for v in _visuals(build_files(spec, frames))}
    assert set(visuals) == {"cardVisual", "clusteredBarChart", "tableEx"}
    card = visuals["cardVisual"]["visual"]["query"]["queryState"]["Data"]["projections"][0]
    assert card["field"] == {"Measure": {"Expression": {"SourceRef": {"Entity": "fact_pmm"}}, "Property": "Net Sales"}}
    assert card["queryRef"] == "fact_pmm.Net Sales"
    bar = visuals["clusteredBarChart"]["visual"]["query"]["queryState"]
    assert bar["Category"]["projections"][0]["field"]["Column"]["Property"] == "product_name"
    assert [list(p["field"])[0] for p in visuals["tableEx"]["visual"]["query"]["queryState"]["Values"]["projections"]] == [
        "Column",
        "Measure",
    ]
    for v in _visuals(build_files(spec, frames)):  # keys the Desktop template visuals have
        assert {"name", "position", "visual"} <= set(v) and len(v["name"]) == 20


def test_layout_is_deterministic_and_inside_the_page(spec, frames):
    first, second = build_files(spec, frames), build_files(spec, frames)
    assert first == second
    for v in _visuals(first):
        p = v["position"]
        assert p["x"] >= 0 and p["y"] >= 0 and p["x"] + p["width"] <= 1920


def test_infeasible_measure_is_a_gap_never_a_number(spec, frames):
    spec.measures.append(
        Measure(name="Gross-to-Net", kpi_id="KPI-034", expression="", feasible=False, gap_reason="no governed source data")
    )
    spec.pages[0].visuals.append(Visual(type="card", title="Gross to net", measures=["Gross-to-Net"]))
    files = build_files(spec, frames)
    assert "Gross-to-Net" not in files[f"{SM}/definition/tables/fact_pmm.tmdl"]
    assert not any("Gross-to-Net" in t for p, t in files.items() if p.endswith("visual.json"))
    assert "Gap, not in the model: Gross-to-Net (KPI-034): no governed source data" in files["README.txt"]
    assert 'Visual "Gross to net" is not exported' in files["README.txt"]


def test_unknown_visual_type_is_listed_not_guessed(spec, frames):
    spec.pages[0].visuals.append(Visual(type="matrix", title="Matrix", measures=["Net Sales"]))
    files = build_files(spec, frames)
    assert len(_visuals(files)) == 3 and 'Visual "Matrix" (matrix) is not exported' in files["README.txt"]


def test_export_writes_a_zip(tmp_path, spec, frames):
    target = export_pbip(spec, frames, tmp_path)
    assert target.name == f"{NAME}.pbip.zip"
    with zipfile.ZipFile(target) as zf:
        names = set(zf.namelist())
        assert {f"{NAME}.pbip", "README.txt", "spec.json"} <= names
        assert not zf.read("README.txt").startswith(b"\xef\xbb\xbf")  # UTF-8 without BOM
        assert json.loads(zf.read("spec.json"))["name"] == spec.name


def test_req0001_fixture_on_the_real_data_pack():
    spec = DashboardSpec.model_validate_json((ROOT / "tests/bi_steward/fixtures/spec_req0001.json").read_text(encoding="utf-8"))
    files = build_files(spec, load_frames())
    assert len(_visuals(files)) == 7  # 4 cards + line + bar + table
    assert {v["visual"]["visualType"] for v in _visuals(files)} == {"cardVisual", "lineChart", "clusteredBarChart", "tableEx"}
    line = next(v for v in _visuals(files) if v["visual"]["visualType"] == "lineChart")
    props = [p["field"]["Measure"]["Property"] for p in line["visual"]["query"]["queryState"]["Y"]["projections"]]
    assert props == ["Net Sales", "Forecast"]  # the line is shown against the forecast
    assert line["visual"]["query"]["queryState"]["Category"]["projections"][0]["queryRef"] == "dim_month.month"
    for path, text in files.items():
        if path.endswith(".json") or path.endswith(".pbir") or path.endswith(".pbip") or path.endswith(".platform"):
            json.loads(text)


def test_dax_matches_the_python_numbers_on_trap_14_and_months():
    dax = {m.kpi_id: m.expression for m in all_measures()}
    for kpi in ("KPI-016", "KPI-020", "KPI-027"):  # averages leave out the zero-sales rows, as semantic.compute does
        assert "fact_pmm[net_sales_m_eur_syn] > 0" in dax[kpi], kpi
    assert "DATEADD" not in dax["KPI-004"] and "EDATE(cur, -1)" in dax["KPI-004"]  # month-start dates are not contiguous days
    assert "VAR cur = MAX(dim_month[month])" in dax["KPI-004"]  # latest month in a card, each month on a month axis


def test_export_holds_only_the_specs_scope_and_the_fixture_dax_is_the_governed_dax():
    from steward.semantic import compute, measure, scoped_frames

    frames = load_frames()
    scoped = scoped_frames(frames, {"product": "Nubeqa"})
    assert set(scoped["fact_pmm"]["product_id"]) == {"P-NUB"} and list(scoped["dim_product"]["product_id"]) == ["P-NUB"]
    assert list(scoped["fact_pmm"].columns) == list(frames["fact_pmm"].columns)
    full = compute(measure("KPI-001"), frames, {"product": "Nubeqa"})["value"][0]
    assert abs(scoped["fact_pmm"]["net_sales_m_eur_syn"].sum() - full) < 1e-6  # the model sums to what the app shows
    assert len(scoped_frames(frames, {})["fact_pmm"]) == 980
    spec = DashboardSpec.model_validate_json((ROOT / "tests/bi_steward/fixtures/spec_req0001.json").read_text(encoding="utf-8"))
    governed = {m.kpi_id: m.expression for m in all_measures()}
    assert all(m.expression == governed[m.kpi_id] for m in spec.measures if m.kpi_id in governed)
    assert "Scope: the model holds only product = Nubeqa." in build_files(spec, frames)["README.txt"]


def _reading(files: dict[str, str]) -> list[str]:
    """PBIR visual types in tab order (= reading order)."""
    vs = sorted(_visuals(files), key=lambda v: v["position"]["tabOrder"])
    return [v["visual"]["visualType"] for v in vs]


def test_steps_set_the_reading_order_and_tab_order(spec, frames):
    visuals = spec.pages[0].visuals  # card, bar, table
    visuals[0].step, visuals[1].step, visuals[2].step = 3, 1, 2
    files = build_files(spec, frames)
    assert _reading(files) == ["clusteredBarChart", "tableEx", "cardVisual"]
    # the page flows downward in that order: each visual starts at or below the one before it
    ys = [v["position"]["y"] for v in sorted(_visuals(files), key=lambda v: v["position"]["tabOrder"])]
    assert ys == sorted(ys)


def test_unset_steps_keep_the_old_layout_and_unnumbered_visuals_go_last(spec, frames):
    assert _reading(build_files(spec, frames)) == ["cardVisual", "clusteredBarChart", "tableEx"]  # nothing set: as before
    spec.pages[0].visuals[2].step = 1  # only the table is numbered
    assert _reading(build_files(spec, frames)) == ["tableEx", "cardVisual", "clusteredBarChart"]


def test_flow_layout_is_deterministic_and_inside_the_page(spec, frames):
    for n, v in enumerate(spec.pages[0].visuals, 1):
        v.step = 4 - n
    first, second = build_files(spec, frames), build_files(spec, frames)
    assert first == second
    for v in _visuals(first):
        p = v["position"]
        assert p["x"] >= 0 and p["y"] >= 0 and p["x"] + p["width"] <= 1920


def test_flow_groups_neighbouring_cards_and_charts(spec, frames):
    spec.pages[0].visuals = [
        Visual(type="card", title="a", measures=["Net Sales"], step=1),
        Visual(type="card", title="b", measures=["Net Sales"], step=2),
        Visual(type="bar", title="c", measures=["Net Sales"], dimension="product", step=3),
        Visual(type="card", title="d", measures=["Net Sales"], step=4),
    ]
    pos = [v["position"] for v in sorted(_visuals(build_files(spec, frames)), key=lambda v: v["position"]["tabOrder"])]
    assert pos[0]["y"] == pos[1]["y"] and pos[0]["x"] < pos[1]["x"]  # the two cards share a row
    assert pos[2]["y"] > pos[1]["y"] and pos[3]["y"] > pos[2]["y"]  # the chart, then the last card, each on their own row


def _container(spec, frames, title: str, question: str = ""):
    spec.pages[0].visuals = [Visual(type="card", title=title, measures=["Net Sales"], question=question)]
    (v,) = _visuals(build_files(spec, frames))
    return v["visual"]


def test_title_is_the_code_title_and_question_is_only_a_subtitle(spec, frames):
    """Shape and quoting as Desktop saved them in templates/pbip (card with 'Net sales card' / 'How much did we sell?')."""
    card = next(
        json.loads(p.read_text(encoding="utf-8"))
        for p in (TEMPLATE / "definition" / "pages").glob("*/visuals/*/visual.json")
        if json.loads(p.read_text(encoding="utf-8"))["visual"]["visualType"] == "cardVisual"
    )["visual"]["visualContainerObjects"]
    mine = _container(spec, frames, "Net sales", "How much did we sell?")["visualContainerObjects"]
    assert set(mine) == set(card) == {"title", "subTitle"}
    assert set(mine["title"][0]["properties"]) == set(card["title"][0]["properties"]) == {"show", "text"}
    assert set(mine["subTitle"][0]["properties"]) == set(card["subTitle"][0]["properties"]) == {"text"}
    assert mine["title"][0]["properties"]["text"] == {"expr": {"Literal": {"Value": "'Net sales'"}}}
    assert mine["subTitle"][0]["properties"]["text"] == {"expr": {"Literal": {"Value": "'How much did we sell?'"}}}
    assert mine["title"][0]["properties"]["show"] == card["title"][0]["properties"]["show"]


def test_no_question_means_no_subtitle_and_quotes_are_doubled_like_dax(spec, frames):
    v = _container(spec, frames, "Nubeqa's net sales", "")
    assert "subTitle" not in v["visualContainerObjects"]
    assert v["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"] == "'Nubeqa''s net sales'"
    assert list(v) == ["visualType", "query", "visualContainerObjects", "drillFilterOtherVisuals"]  # Desktop's key order
    spec.pages[0].visuals = [Visual(type="card", title="", measures=["Net Sales"])]
    assert "visualContainerObjects" not in _visuals(build_files(spec, frames))[0]["visual"]  # nothing to show, nothing written


# -- overview pages: 12-column grid, kpi_strip, chart types without a Desktop template ------------------------------------


def _visual_class():
    """Visual with span / row: the real one once spec.py has them, else a stand-in with the same field names."""
    if "span" in Visual.model_fields:
        return Visual

    class _Visual(Visual):
        span: int | None = None
        row: int | None = None

    return _Visual


def _overview(spec, visuals, extra_measures=()):
    spec.measures += list(extra_measures)
    spec.pages[0].visuals = visuals
    return spec


def _placed(files):
    """title -> (x, y, width, height), from the exported visual.json files."""
    out = {}
    for v in _visuals(files):
        title = v["visual"]["visualContainerObjects"]["title"][0]["properties"]["text"]["expr"]["Literal"]["Value"].strip("'")
        p = v["position"]
        out[title] = (p["x"], p["y"], p["width"], p["height"])
    return out


def test_spans_are_placed_on_a_12_column_grid(spec, frames):
    V = _visual_class()
    cards = [V(type="card", title=f"c{i}", measures=["Net Sales"], span=4) for i in range(3)]
    placed = _placed(build_files(_overview(spec, cards), frames))
    xs = sorted(placed[f"c{i}"][0] for i in range(3))
    assert len({placed[f"c{i}"][1] for i in range(3)}) == 1 and xs == sorted(set(xs))  # one row, three columns
    assert len({placed[f"c{i}"][2] for i in range(3)}) == 1
    last = max(placed.values())  # right edge of the last tile touches the page margin
    assert last[0] + last[2] == 1920 - 20 and min(x for x, *_ in placed.values()) == 20


def test_a_row_wraps_when_the_12_columns_are_full_and_span_8_plus_4_share_a_row(spec, frames):
    V = _visual_class()
    visuals = [
        V(type="bar", title="wide", measures=["Net Sales"], dimension="product", span=8),
        V(type="card", title="narrow", measures=["Net Sales"], span=4),
        V(type="bar", title="next", measures=["Net Sales"], dimension="product", span=6),
    ]
    placed = _placed(build_files(_overview(spec, visuals), frames))
    assert placed["wide"][1] == placed["narrow"][1] and placed["wide"][2] > 1.9 * placed["narrow"][2]
    assert placed["next"][1] > placed["wide"][1]  # 8 + 4 = 12 is full: the next one starts a new row


def test_explicit_rows_come_in_ascending_order_whatever_the_listing_order(spec, frames):
    V = _visual_class()
    visuals = [
        V(type="card", title="second", measures=["Net Sales"], span=6, row=2),
        V(type="card", title="first", measures=["Net Sales"], span=6, row=1),
    ]
    placed = _placed(build_files(_overview(spec, visuals), frames))
    assert placed["first"][1] < placed["second"][1]


def test_kpi_strip_becomes_one_card_per_measure_in_one_row_and_drops_gaps_with_a_note(spec, frames):
    V = _visual_class()
    units = Measure(name="Units", kpi_id="KPI-014", expression="SUM(fact_pmm[units])", format="#,##0")
    gap = Measure(name="Gross-to-Net Rate", kpi_id="KPI-034", feasible=False, gap_reason="no source data")
    strip = V(type="kpi_strip", title="Status", measures=["Net Sales", "Units", "Gross-to-Net Rate"])
    files = build_files(_overview(spec, [strip], [units, gap]), frames)
    placed = _placed(files)
    assert set(placed) == {"Net Sales", "Units"}  # the gap tile is not exported
    (x1, y1, w1, _), (x2, y2, w2, _) = placed["Net Sales"], placed["Units"]
    assert y1 == y2 and x2 > x1 and w1 == w2 and x2 + w2 == 1920 - 20  # two equal tiles share the full width
    assert 'Tile "Gross-to-Net Rate" of "Status" is not exported' in files["README.txt"]


def test_kpi_strip_shows_at_most_eight_measures(spec, frames):
    V = _visual_class()
    many = [Measure(name=f"M{i}", kpi_id="", expression="SUM(fact_pmm[units])") for i in range(9)]
    strip = V(type="kpi_strip", title="Everything", measures=[m.name for m in many])
    files = build_files(_overview(spec, [strip], many), frames)
    assert len(_visuals(files)) == 8 and "first 8 measures; 1 more are left out" in files["README.txt"]


def test_new_chart_types_are_drawn_as_clustered_bars_with_a_note(spec, frames):
    V = _visual_class()
    visuals = [
        V(type=t, title=f"as {t}", measures=["Net Sales"], dimension="product", span=6)
        for t in ("bullet", "diverging_bar", "stacked_100")
    ]
    files = build_files(_overview(spec, visuals), frames)
    assert [v["visual"]["visualType"] for v in _visuals(files)] == ["clusteredBarChart"] * 3
    for t in ("bullet", "diverging_bar", "stacked_100"):
        assert f'Visual "as {t}" ({t}) is drawn as a clustered bar chart' in files["README.txt"]


def test_specs_without_span_or_row_export_exactly_as_before(spec, frames):
    """The default layout is untouched: same files whether the visuals are plain Visuals or carry empty span / row."""
    V = _visual_class()
    plain = build_files(spec, frames)
    spec.pages[0].visuals = [V(**v.model_dump()) for v in spec.pages[0].visuals]
    assert build_files(spec, frames) == plain


def test_on_an_overview_page_unnumbered_visuals_keep_the_listed_order(spec, frames):
    """A kpi_strip without a step must stay on top; steps re-order only when every visual has one."""
    V = _visual_class()
    visuals = [
        V(type="card", title="first", measures=["Net Sales"], span=12),
        V(type="bar", title="second", measures=["Net Sales"], dimension="product", span=12, step=1),
    ]
    placed = _placed(build_files(_overview(spec, visuals), frames))
    assert placed["first"][1] < placed["second"][1]
    for v in visuals:
        v.step = 2 if v.title == "first" else 1  # fully numbered now: the steps decide
    placed = _placed(build_files(_overview(spec, visuals), frames))
    assert placed["second"][1] < placed["first"][1]
