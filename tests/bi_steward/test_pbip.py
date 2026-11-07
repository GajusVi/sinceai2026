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
    assert "DATEADD" not in dax["KPI-004"] and "EDATE" in dax["KPI-004"]  # month-start dates are not contiguous days
