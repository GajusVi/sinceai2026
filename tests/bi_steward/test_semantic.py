"""N2: the governed semantic layer. Numbers are checked against an independent pandas calculation of the raw sheets."""
import pandas as pd
import pytest

from steward.datapack import DEFAULT_XLSX
from steward.intent import Intent
from steward.semantic import all_measures, compute, feasibility, forecast, load_frames, measure, star_schema

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture(scope="module")
def frames():
    return load_frames()


@pytest.fixture(scope="module")
def raw():
    return pd.read_excel(DEFAULT_XLSX, sheet_name="Product_Market_Monthly")


def test_18_canonical_measures_12_bound_6_gaps():
    ms = all_measures()
    assert len(ms) == 18
    gaps = sorted(m.kpi_id for m in ms if not m.feasible)
    assert gaps == ["KPI-023", "KPI-034", "KPI-037", "KPI-039", "KPI-046", "KPI-049"]
    assert all(m.expression and m.source for m in ms if m.feasible)
    assert all(m.gap_reason and not m.expression for m in ms if not m.feasible)


def test_req0001_is_fully_buildable():
    f = feasibility(Intent(products=["Nubeqa"], markets=["Global"],
                           metric_ids=["net_sales_growth", "forecast_variance", "market_access_coverage"]))
    assert [m.kpi_id for m in f.buildable] == ["KPI-004", "KPI-042", "KPI-027"]
    assert not f.gaps and f.scope_ok and not f.nearest


def test_template_2_has_one_buildable_measure_and_two_gaps_with_a_nearest_offer():
    f = feasibility(Intent(products=["All Pharma"], metric_ids=["net_sales", "gross_to_net_rate", "budget_variance"]))
    assert [m.kpi_id for m in f.buildable] == ["KPI-001"]
    assert [m.kpi_id for m in f.gaps] == ["KPI-034", "KPI-039"]
    assert "KPI-042 Forecast Variance" in f.nearest  # buildable, same domain (Finance)


def test_scope_and_unknown_ids():
    assert not feasibility(Intent(products=["Aspirin"], metric_ids=["net_sales"])).scope_ok
    assert not feasibility(Intent(markets=["XX"], metric_ids=["net_sales"])).scope_ok
    f = feasibility(Intent(metric_ids=["batch_yield", "KPI-001"]))
    assert f.unknown == ["batch_yield"] and [m.kpi_id for m in f.buildable] == ["KPI-001"]


def test_net_sales_matches_the_raw_sheet(frames, raw):
    nub = raw[raw.product_id == "P-NUB"]
    total = compute(measure("KPI-001"), frames, {"product": "Nubeqa"})
    assert total["value"].iloc[0] == pytest.approx(nub.net_sales_m_eur_syn.sum())
    by_month = compute(measure("KPI-001"), frames, {"product": "P-NUB"}, by="month")
    assert len(by_month) == 10 and by_month["value"].sum() == pytest.approx(nub.net_sales_m_eur_syn.sum())
    de = compute(measure("KPI-001"), frames, {"product": "Nubeqa", "market": "DE"})
    assert de["value"].iloc[0] == pytest.approx(nub[nub.market_id == "DE"].net_sales_m_eur_syn.sum())
    emea = compute(measure("KPI-001"), frames, {"region": "EMEA"})
    in_emea = raw[raw.market_id.isin(["DE", "FR", "IT", "ES", "FI", "SE", "UK"])]
    assert emea["value"].iloc[0] == pytest.approx(in_emea.net_sales_m_eur_syn.sum())


def test_forecast_variance_and_growth(frames, raw):
    nub = raw[(raw.product_id == "P-NUB") & ~((raw.net_sales_m_eur_syn == 0) & raw.forecast_variance_pct.isna())]
    var = compute(measure("KPI-042"), frames, {"product": "Nubeqa"})
    assert var["value"].iloc[0] == pytest.approx(nub.net_sales_m_eur_syn.sum() - nub.forecast_m_eur_syn.sum())
    monthly = raw[raw.product_id == "P-NUB"].groupby("month").net_sales_m_eur_syn.sum().sort_index()
    growth = compute(measure("KPI-004"), frames, {"product": "Nubeqa"})
    assert growth["value"].iloc[0] == pytest.approx(monthly.iloc[-1] / monthly.iloc[-2] - 1)
    by_market = compute(measure("KPI-004"), frames, {"product": "Nubeqa"}, by="market")
    assert set(by_market.columns) == {"market_id", "value"} and len(by_market) > 1
    fc = forecast(frames, {"product": "Nubeqa"}, by="month")
    assert fc["value"].sum() == pytest.approx(raw[raw.product_id == "P-NUB"].forecast_m_eur_syn.sum())


def test_zero_sales_rows_are_left_out_of_averages_and_reported(frames, raw):
    out = compute(measure("KPI-016"), frames)  # inventory coverage: an average
    kept = raw[~((raw.net_sales_m_eur_syn == 0) & raw.forecast_variance_pct.isna())]
    assert out["value"].iloc[0] == pytest.approx(kept.inventory_weeks_syn.mean())
    assert any("110 zero-sales rows" in note for note in out.attrs["dq"])


def test_a_gap_is_never_a_number(frames):
    with pytest.raises(ValueError, match="gap"):
        compute(measure("KPI-034"), frames)


def test_snapshot_and_asset_measures(frames):
    with pytest.raises(ValueError, match="no monthly trend"):
        compute(measure("KPI-031"), frames, by="month")
    listed = compute(measure("KPI-031"), frames, by="market")
    assert listed["value"].between(0, 100).all()
    cert = compute(measure("KPI-054"), frames)
    assert 0 < cert["value"].iloc[0] < 100
    adoption = compute(measure("KPI-051"), frames, by="month")
    assert len(adoption) == 10 and (adoption["value"] > 0).all()


def test_star_schema_has_the_dims_and_relationships():
    entities, columns, rel = star_schema()
    assert {"fact_pmm", "dim_product", "dim_market", "dim_month"} <= set(entities)
    assert {"region"} <= set(columns["dim_market"]) and "net_sales_m_eur_syn" in columns["fact_pmm"]
    pmm = {(r.to_entity, r.key) for r in rel if r.from_entity == "fact_pmm"}
    assert pmm == {("dim_product", "product_id"), ("dim_market", "market_id"), ("dim_month", "month")}
    assert all(r.cardinality == "many_to_one" for r in rel)


def test_site_filter_keeps_only_the_pairs_the_site_supplies():
    from steward import semantic

    frames = semantic.load_frames()
    otif = semantic.measure("KPI-020")
    everything = semantic.compute(otif, frames, {}, by="product")
    plant_b = semantic.compute(otif, frames, {"site": "Plant-B"}, by="product")
    assert 0 < len(plant_b) <= len(everything)
    supply = frames["fact_supply"]
    scoped = semantic._scope(frames["fact_pmm"], {"site": "Plant-B"}, frames)
    pairs = set(zip(supply.loc[supply.supply_source == "Plant-B", "product_id"],
                    supply.loc[supply.supply_source == "Plant-B", "market_id"], strict=True))
    assert set(zip(scoped.product_id, scoped.market_id, strict=True)) <= pairs


def test_forecast_like_rows_are_reported_not_hidden(frames):
    out = compute(measure("KPI-001"), frames)
    assert any("forecast_like" in note and "used as actuals" in note for note in out.attrs["dq"])
