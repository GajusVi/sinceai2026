"""Structure checks for the draft .PBIP export. Not opened in Power BI Desktop: these tests only check layout and syntax rules
taken from Microsoft's PBIP and TMDL docs."""

import json
import zipfile

import pandas as pd
import pytest

from steward.pbip import _q, _safe_name, build_files, export_pbip
from steward.spec import DashboardSpec, Measure, Page, Relationship, Visual


@pytest.fixture
def frames():
    return {
        "fact_pmm": pd.DataFrame(
            {
                "product_id": ["P-NUB", "P-NUB"],
                "market_id": ["DE", "FR"],
                "month": pd.to_datetime(["2026-01-01", "2026-02-01"]),
                "net_sales": [1.5, 2.5],
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
            Page(name="What needs attention", visuals=[Visual(type="card", title="Net sales", measures=["Net Sales"])])
        ],
    )


def test_names_are_safe_and_short():
    assert _safe_name("Nubeqa net sales (draft)") == "Nubeqa_net_sales_draft"
    assert len(_safe_name("x" * 200)) <= 40 and _safe_name("???") == "dashboard"


def test_tmdl_quoting_follows_the_docs():
    assert _q("fact_pmm") == "fact_pmm"
    assert _q("Net Sales") == "'Net Sales'" and _q("a.b") == "'a.b'" and _q("it's") == "'it''s'"


def test_folder_layout_matches_the_pbip_docs(spec, frames):
    files = build_files(spec, frames)
    name = "Nubeqa_net_sales_draft"
    for path in (
        f"{name}.pbip",
        f"{name}.SemanticModel/definition.pbism",
        f"{name}.SemanticModel/definition/database.tmdl",
        f"{name}.SemanticModel/definition/model.tmdl",
        f"{name}.SemanticModel/definition/relationships.tmdl",
        f"{name}.SemanticModel/definition/tables/fact_pmm.tmdl",
        f"{name}.SemanticModel/definition/tables/dim_product.tmdl",
        f"{name}.Report/definition.pbir",
        "README.txt",
        "spec.json",
    ):
        assert path in files, path
    pbip = json.loads(files[f"{name}.pbip"])
    assert pbip["artifacts"] == [{"report": {"path": f"{name}.Report"}}]
    assert (
        json.loads(files[f"{name}.SemanticModel/definition.pbism"])["version"] == "4.0"
    )  # 4.0+ allows the TMDL definition folder
    pbir = json.loads(files[f"{name}.Report/definition.pbir"])
    assert pbir["datasetReference"]["byPath"]["path"] == f"../{name}.SemanticModel"  # relative, forward slashes


def test_tables_have_measures_columns_and_a_partition(spec, frames):
    files = build_files(spec, frames)
    fact = files["Nubeqa_net_sales_draft.SemanticModel/definition/tables/fact_pmm.tmdl"]
    assert fact.startswith("table fact_pmm\n")
    assert "\tmeasure 'Net Sales' = SUM(fact_pmm[net_sales])\n\t\tformatString: #,##0.0" in fact
    assert "\tcolumn net_sales\n\t\tdataType: double\n\t\tsourceColumn: net_sales" in fact
    assert "dataType: int64" in fact and "dataType: dateTime" in fact and "dataType: string" in fact
    assert "partition fact_pmm-Partition = m" in fact.replace("'", "") and "File.Contents(DataFolder" in fact
    assert (
        "measure" not in files["Nubeqa_net_sales_draft.SemanticModel/definition/tables/dim_product.tmdl"]
    )  # measures only on the fact table
    assert all(
        not line.startswith(" ")
        for text in files.values()
        for line in text.splitlines()
        if line.strip() and text.startswith(("table", "model"))
    )  # tabs, never spaces


def test_relationship_and_model_refs(spec, frames):
    definition = "Nubeqa_net_sales_draft.SemanticModel/definition/"
    files = build_files(spec, frames)
    rel = files[definition + "relationships.tmdl"]
    assert (
        rel.startswith("relationship ")
        and "\tfromColumn: fact_pmm.product_id\n\ttoColumn: dim_product.product_id" in rel
    )
    assert rel == build_files(spec, frames)[definition + "relationships.tmdl"]  # deterministic ids
    assert "ref table fact_pmm\nref table dim_product\n" in files[definition + "model.tmdl"]
    assert "DataFolder" in files[definition + "expressions.tmdl"]


def test_export_writes_a_zip_with_csv_data_and_draft_label(tmp_path, spec, frames):
    target = export_pbip(spec, frames, tmp_path)
    assert target.name == "Nubeqa_net_sales_draft.pbip.zip"
    with zipfile.ZipFile(target) as zf:
        names = set(zf.namelist())
        assert {"data/fact_pmm.csv", "data/dim_product.csv", "README.txt", "spec.json"} <= names
        assert zf.read("data/dim_product.csv").decode("utf-8").splitlines() == [
            "product_id,product_name",
            "P-NUB,Nubeqa",
        ]
        assert not zf.read("README.txt").startswith(b"\xef\xbb\xbf")  # UTF-8 without BOM
        assert "not opened in Power BI Desktop yet" in zf.read("README.txt").decode("utf-8")
        assert json.loads(zf.read("spec.json"))["name"] == spec.name


@pytest.mark.skipif("feasible" not in Measure.model_fields, reason="spec v2 (Measure.feasible) not on main yet")
def test_infeasible_measure_is_a_gap_never_a_number(spec, frames):
    spec.measures.append(
        Measure(
            name="Gross-to-Net", kpi_id="KPI-034", expression="", feasible=False, gap_reason="no governed source data"
        )
    )
    files = build_files(spec, frames)
    assert "Gross-to-Net" not in files["Nubeqa_net_sales_draft.SemanticModel/definition/tables/fact_pmm.tmdl"]
    assert "Gap, not in the model: Gross-to-Net (KPI-034): no governed source data" in files["README.txt"]
