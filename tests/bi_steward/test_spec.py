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
