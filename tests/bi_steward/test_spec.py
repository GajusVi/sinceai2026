from pathlib import Path

import pandas as pd

from steward.datapack import DEFAULT_XLSX
from steward.spec import DashboardSpec, Measure, Page, Relationship, Visual


def example() -> DashboardSpec:
    return DashboardSpec(
        name="Nubeqa Germany: Net Sales vs Forecast",
        entities=["Product_Market_Monthly", "Products", "Markets"],
        columns={
            "Product_Market_Monthly": ["month", "product_id", "market_id", "net_sales_m_eur_syn", "forecast_m_eur_syn"],
            "Products": ["product_id", "product_name"],
            "Markets": ["market_id", "market_name", "region"],
        },
        grain={"Product_Market_Monthly": "month"},
        relationships=[
            Relationship(from_entity="Product_Market_Monthly", to_entity="Products", key="product_id"),
            Relationship(from_entity="Product_Market_Monthly", to_entity="Markets", key="market_id"),
        ],
        measures=[
            Measure(name="Net Sales", kpi_id="KPI-001", expression="SUM(net_sales_m_eur_syn)", format="EUR"),
            Measure(name="Forecast Variance", kpi_id="KPI-042", expression="SUM(net_sales_m_eur_syn) - SUM(forecast_m_eur_syn)", format="EUR"),
        ],
        pages=[
            Page(
                name="Overview",
                visuals=[
                    Visual(type="card", title="Net Sales", measures=["Net Sales"]),
                    Visual(type="line", title="Net Sales by month", measures=["Net Sales"], dimension="month"),
                    Visual(type="bar", title="Forecast Variance by month", measures=["Forecast Variance"], dimension="month"),
                ],
            )
        ],
        filters={"product": "Nubeqa", "market": "DE"},
        kpi_ids=["KPI-001", "KPI-042"],
        source_model_id="SM-001",
        owner_id="OWN-041",
        rationale="No existing asset covers both KPIs for Nubeqa in Germany at monthly grain.",
    )


def test_spec_roundtrip():
    spec = example()
    again = DashboardSpec.model_validate_json(spec.model_dump_json())
    assert again == spec
    assert {m.kpi_id for m in again.measures} == set(again.kpi_ids)
    names = {m.name for m in again.measures}
    assert all(set(v.measures) <= names for p in again.pages for v in p.visuals)


# --- v2 (C5): the REQ-0001 EXTEND fixture that lint, render and specbuild are built against ---
FIXTURE = Path(__file__).parent / "fixtures" / "spec_req0001.json"


def fixture() -> DashboardSpec:
    return DashboardSpec.model_validate_json(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_validates_and_is_self_consistent():
    spec = fixture()
    assert spec.verdict == "EXTEND" and spec.change_type == "extend" and spec.base_asset_ids == ["AST-0335"]
    names = {m.name for m in spec.measures}
    visuals = [v for p in spec.pages for v in p.visuals]
    assert all(set(v.measures) <= names for v in visuals)
    assert {m.kpi_id for m in spec.measures} == set(spec.kpi_ids)
    assert len(spec.pages) <= 2 and len(visuals) <= 7 and sum(v.type == "card" for v in visuals) <= 4
    assert all(c.record_ids for c in spec.changes)  # RULE-008
    assert all(m.feasible and m.definition_status == "canonical" for m in spec.measures)


def test_fixture_record_ids_exist_in_the_data_pack():
    spec = fixture()
    sheets = pd.read_excel(DEFAULT_XLSX, sheet_name=["Analytics_Assets", "KPI_Catalog", "Owners", "Semantic_Models"])
    known = (
        set(sheets["Analytics_Assets"].asset_id) | set(sheets["KPI_Catalog"].kpi_id)
        | set(sheets["Owners"].owner_id) | {"dim_market"}
    )
    cited = {r for c in spec.changes for r in c.record_ids}
    assert cited <= known, cited - known
    assert spec.source_model_id in set(sheets["Semantic_Models"].model_id)
    assert spec.owner_id in set(sheets["Owners"].owner_id)


def test_v2_fields_all_default_so_the_old_spec_still_validates():
    old = DashboardSpec(name="x")
    assert old.verdict == "" and old.lint == [] and old.platform == "Power BI" and old.version == 1
    assert Measure(name="m", kpi_id="KPI-001").feasible is True
