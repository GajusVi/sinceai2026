"""The governed semantic layer (BUILD_PLAN section 4): a star schema over the data pack, KPI-to-measure bindings,
feasibility of an Intent and deterministic computation of a measure.

NIGHT draft by Gajus (Sat 7 Nov); back to Martynas at 08:00 for review. Choices made here, flagged for him:
- KPI-051 Report Adoption is bound to the average monthly unique users per asset (unit "users"), not the catalog "%",
  because the only percentage available would divide by estimated_audience, which the data pack says not to trust.
- fact_supply, fact_access, dim_asset are snapshots (no month column): no trend for them (grain "snapshot").
- Trap 14: rows with zero sales and null forecast variance are left out of averages and ratios, with a DQ note.
Everything is synthetic and every render must say so (DashboardSpec.data_label).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

import pandas as pd

from .config import ROOT_DIR
from .datapack import ALL_PHARMA, DEFAULT_XLSX, GLOBAL
from .intent import Intent
from .spec import Measure, Relationship

BAYER_DIR = ROOT_DIR / "catalog" / "bayer"
ASSET_LEVEL_KPIS = {"KPI-051", "KPI-054"}  # asset-level data: no product / market breakdown
BY_COLUMN = {"month": "month", "market": "market_id", "product": "product_name", "region": "region"}


@dataclass
class Feasibility:
    buildable: list[Measure] = field(default_factory=list)
    gaps: list[Measure] = field(default_factory=list)  # governed KPIs without source data
    scope_ok: bool = True  # every named product / market / region exists in the facts
    nearest: list[str] = field(default_factory=list)  # buildable alternatives for the gaps, "KPI-001 Net Sales"
    unknown: list[str] = field(default_factory=list)  # requested ids that are not in the KPI catalog at all


# -- data ---------------------------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def load_frames() -> dict[str, pd.DataFrame]:
    """fact_* and dim_* tables, read once. Treat them as read-only."""
    sheets = pd.read_excel(
        DEFAULT_XLSX,
        sheet_name=[
            "Product_Market_Monthly",
            "Supply_Operations",
            "Market_Access",
            "Launch_Milestones",
            "Asset_Usage",
            "Analytics_Assets",
            "Products",
            "Markets",
        ],
    )
    regions = json.loads((BAYER_DIR / "regions.json").read_text(encoding="utf-8"))
    region_of = {m: r for r, members in regions.items() for m in members}
    pmm = sheets["Product_Market_Monthly"]
    pmm["month"] = pd.to_datetime(pmm["month"])
    usage = sheets["Asset_Usage"]
    usage["month"] = pd.to_datetime(usage["month"])
    markets = sheets["Markets"][["market_id", "market_name", "region"]].copy()
    markets["region"] = markets["market_id"].map(region_of).fillna(markets["region"])
    return {
        "fact_pmm": pmm,
        "fact_supply": sheets["Supply_Operations"],
        "fact_access": sheets["Market_Access"],
        "fact_launch": sheets["Launch_Milestones"],
        "fact_usage": usage,
        "dim_asset": sheets["Analytics_Assets"],
        "dim_product": sheets["Products"][["product_id", "product_name", "therapeutic_area"]],
        "dim_market": markets,
        "dim_month": pd.DataFrame({"month": sorted(pmm["month"].unique())}),
    }


def star_schema() -> tuple[list[str], dict[str, list[str]], list[Relationship]]:
    frames = load_frames()
    entities = list(frames)
    columns = {name: list(df.columns) for name, df in frames.items() if name != "fact_launch"}
    columns["fact_launch"] = list(frames["fact_launch"].columns)
    rel = [
        Relationship(from_entity="fact_pmm", to_entity="dim_product", key="product_id"),
        Relationship(from_entity="fact_pmm", to_entity="dim_market", key="market_id"),
        Relationship(from_entity="fact_pmm", to_entity="dim_month", key="month"),
        Relationship(from_entity="fact_supply", to_entity="dim_product", key="product_id"),
        Relationship(from_entity="fact_supply", to_entity="dim_market", key="market_id"),
        Relationship(from_entity="fact_access", to_entity="dim_product", key="product_id"),
        Relationship(from_entity="fact_access", to_entity="dim_market", key="market_id"),
        Relationship(from_entity="fact_launch", to_entity="dim_product", key="product_id"),
        Relationship(from_entity="fact_launch", to_entity="dim_market", key="market_id"),
        Relationship(from_entity="fact_usage", to_entity="dim_asset", key="asset_id"),
        Relationship(from_entity="fact_usage", to_entity="dim_month", key="month"),
    ]
    return entities, columns, rel


# -- measures -----------------------------------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _entries() -> dict[str, dict]:
    return {e["kpi_id"]: e for e in json.loads((BAYER_DIR / "measures.json").read_text(encoding="utf-8"))}


def measure(kpi_id: str) -> Measure:
    """The canonical measure of a governed KPI. Infeasible ones come back with feasible=False and a gap_reason."""
    e = _entries()[kpi_id]
    return Measure(
        name=e["name"],
        kpi_id=kpi_id,
        expression=e["dax"],
        format=e["format"],
        unit=e["unit"],
        source=e["source"],
        aggregation=e["aggregation"],
        definition_status="canonical",
        feasible=e["feasible"],
        gap_reason=e["gap_reason"],
    )


def all_measures() -> list[Measure]:
    return [measure(k) for k in _entries()]


def grain_of(kpi_id: str) -> str:
    """ "month" = can be trended; "snapshot" = one value per product x market; "" = infeasible."""
    return _entries()[kpi_id]["grain"]


@lru_cache(maxsize=1)
def _slug_to_kpi() -> dict[str, str]:
    metrics = json.loads((BAYER_DIR / "metrics.json").read_text(encoding="utf-8"))
    return {m["id"]: m["kpi_id"] for m in metrics}


def feasibility(intent: Intent) -> Feasibility:
    """Can governed data answer the Intent? Metric ids may be slugs ("net_sales") or KPI ids ("KPI-001")."""
    frames = load_frames()
    result = Feasibility()
    for mid in intent.metric_ids:
        kpi = mid if mid in _entries() else _slug_to_kpi().get(mid, "")
        if not kpi or kpi not in _entries():
            result.unknown.append(mid)
            continue
        (result.buildable if _entries()[kpi]["feasible"] else result.gaps).append(measure(kpi))

    products = set(frames["dim_product"]["product_name"]) | {ALL_PHARMA}
    markets = set(frames["dim_market"]["market_id"]) | {GLOBAL}
    regions = set(frames["dim_market"]["region"])
    sites = set(frames["fact_supply"]["supply_source"].dropna())
    result.scope_ok = (
        all(s in sites for s in intent.sites)
        and all(p in products for p in intent.products)
        and all(m in markets for m in intent.markets)
        and all(r in regions for r in intent.regions)
    )
    for gap in result.gaps:  # nearest governed alternatives: buildable KPIs of the same domain, else the headline ones
        domain = _entries()[gap.kpi_id]["domain"]
        same = [k for k, e in _entries().items() if e["feasible"] and e["domain"] == domain]
        for k in same or ["KPI-001", "KPI-042"]:
            label = f"{k} {_entries()[k]['name']}"
            if label not in result.nearest and k not in {m.kpi_id for m in result.buildable}:
                result.nearest.append(label)
    return result


# -- computing ----------------------------------------------------------------------------------------------------


def _scope(df: pd.DataFrame, filters: dict[str, str], frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Product / market / region filters on a fact with product_id and market_id. Global / All Pharma = no filter."""
    out = df.merge(frames["dim_product"][["product_id", "product_name"]], on="product_id", how="left")
    out = out.merge(frames["dim_market"][["market_id", "region"]], on="market_id", how="left")
    out = _months(out, filters)
    site = filters.get("site")
    if site:  # a supply site = the product x market pairs it supplies (Supply_Operations.supply_source)
        supply = frames["fact_supply"]
        pairs = supply.loc[supply["supply_source"] == site, ["product_id", "market_id"]].drop_duplicates()
        keys = ["product_id", "market_id"]
        out = out[out.set_index(keys).index.isin(pairs.set_index(keys).index)]
    product = filters.get("product")
    if product and product != ALL_PHARMA:
        out = out[(out["product_id"] == product) | (out["product_name"].str.lower() == product.lower())]
    market = filters.get("market")
    if market and market != GLOBAL:
        out = out[out["market_id"] == market]
    region = filters.get("region")
    if region:
        out = out[out["region"] == region]
    return out


def _months(df: pd.DataFrame, filters: dict[str, str]) -> pd.DataFrame:
    """Optional filters["month_from"] / ["month_to"] as "YYYY-MM" (inclusive) on facts that have a month column."""
    if "month" not in df.columns:
        return df
    if filters.get("month_from"):
        df = df[df["month"] >= pd.Timestamp(filters["month_from"] + "-01")]
    if filters.get("month_to"):
        df = df[df["month"] <= pd.Timestamp(filters["month_to"] + "-01")]
    return df


def _scope_assets(df: pd.DataFrame, filters: dict[str, str], frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Asset-level facts (usage, certification): an asset counts for a product or market if its scope covers it."""
    out = df
    product = filters.get("product")
    if product and product != ALL_PHARMA:
        name = frames["dim_product"].set_index("product_id")["product_name"].get(product, product)
        out = out[out["product_scope"].isin([name, ALL_PHARMA])]
    market = filters.get("market")
    if market and market != GLOBAL:
        out = out[out["market_scope"].isin([market, GLOBAL])]
    return out


def _result(rows: list[tuple], by: str | None, dq: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows, columns=[BY_COLUMN[by] if by else "scope", "value"])
    if not by:
        frame["scope"] = "all"
    frame.attrs["dq"] = dq
    return frame


def _group_value(df: pd.DataFrame, e: dict, by: str | None) -> list[tuple]:
    """Aggregate one frame, per group when `by` is set."""
    key = BY_COLUMN[by] if by else None
    groups = [(None, df)] if key is None else [(k, g) for k, g in df.groupby(key)]
    rows = []
    for k, g in groups:
        rows.append((k, _aggregate(g, e)))
    return [(k if k is not None else "all", v) for k, v in rows]


def _aggregate(g: pd.DataFrame, e: dict) -> float:
    derived, col = e["derived"], e["column"]
    if derived == "bias":
        return float((g["net_sales_m_eur_syn"].sum() - g["forecast_m_eur_syn"].sum()) / g["forecast_m_eur_syn"].sum())
    if derived == "variance":
        return float(g["net_sales_m_eur_syn"].sum() - g["forecast_m_eur_syn"].sum())
    if derived == "share_listed":
        return float((g["reimbursement_status"] == "listed").mean() * 100)
    if derived == "share_certified":
        return float((g["endorsement"] == "certified").mean() * 100)
    return float(g[col].sum() if e["aggregation"] == "sum" else g[col].mean())


def compute(
    m: Measure, frames: dict[str, pd.DataFrame], filters: dict[str, str] | None = None, by: str | None = None
) -> pd.DataFrame:
    """A measure over the governed data, optionally by month | market | product | region. Columns: (<by>, "value").
    `result.attrs["dq"]` lists data-quality notes. An infeasible measure raises: it renders as a gap, never a number."""
    if not m.feasible:
        raise ValueError(f"{m.kpi_id} {m.name} is a gap, not computable: {m.gap_reason}")
    e = _entries()[m.kpi_id]
    filters = filters or {}
    dq: list[str] = []
    table = e["table"]
    if table in ("fact_pmm", "fact_supply", "fact_access"):
        df = _scope(frames[table], filters, frames)
        if table == "fact_pmm" and e["exclude_zero_rows"]:
            bad = (df["net_sales_m_eur_syn"] == 0) & df["forecast_variance_pct"].isna()
            if bad.any():
                dq.append(
                    f"{int(bad.sum())} zero-sales rows with no forecast variance were left out of this figure (trap 14)"
                )
            df = df[~bad]
    elif table == "fact_usage":
        assets = _scope_assets(frames["dim_asset"], filters, frames)[["asset_id", "created_date"]]
        df = _months(frames["fact_usage"], filters).merge(assets, on="asset_id")
        df = df[
            df["month"] >= df["created_date"].dt.to_period("M").dt.to_timestamp()
        ]  # usage before creation is a DQ finding
        df = df.merge(frames["dim_asset"][["asset_id", "product_scope", "market_scope"]], on="asset_id")
    else:  # dim_asset
        df = _scope_assets(frames["dim_asset"], filters, frames)
    if by == "month" and e["grain"] != "month":
        raise ValueError(f"{m.kpi_id} {m.name} has no monthly trend (snapshot data)")
    if by in ("market", "product", "region") and table in ("fact_usage", "dim_asset"):
        raise ValueError(f"{m.kpi_id} {m.name} cannot be broken down by {by} (asset-level data)")
    if df.empty:
        dq.append("no rows for this scope")
        return _result([], by, dq)

    if e["derived"] == "growth":  # latest month against the month before, per group
        key = BY_COLUMN[by] if by and by != "month" else None
        monthly = df.groupby(([key] if key else []) + ["month"])["net_sales_m_eur_syn"].sum().reset_index()
        rows = []
        for k, g in monthly.groupby(key) if key else [(None, monthly)]:
            series = g.set_index("month")["net_sales_m_eur_syn"].sort_index() if by != "month" else None
            if by == "month":
                growth = g.set_index("month")["net_sales_m_eur_syn"].sort_index().pct_change().dropna()
                rows += [(ts, float(v)) for ts, v in growth.items()]
            elif len(series) >= 2 and series.iloc[-2] != 0:
                rows.append((k if k is not None else "all", float(series.iloc[-1] / series.iloc[-2] - 1)))
        return _result(rows, by, dq)
    return _result(_group_value(df, e, by), by, dq)


def forecast(frames: dict[str, pd.DataFrame], filters: dict[str, str] | None = None, by: str | None = None,
             exclude_zero: bool = False) -> pd.DataFrame:
    """Forecast (EUR M) from fact_pmm in the same shape as compute(): the comparison next to net sales.
    `exclude_zero` applies the trap-14 exclusion, to match measures that leave those rows out (forecast variance)."""
    df = _scope(frames["fact_pmm"], filters or {}, frames)
    if exclude_zero:
        df = df[~((df["net_sales_m_eur_syn"] == 0) & df["forecast_variance_pct"].isna())]
    key = BY_COLUMN[by] if by else None
    if key:
        rows = [(k, float(g["forecast_m_eur_syn"].sum())) for k, g in df.groupby(key)]
    else:
        rows = [("all", float(df["forecast_m_eur_syn"].sum()))]
    frame = pd.DataFrame(rows, columns=[key or "scope", "value"])
    frame.attrs["dq"] = []
    return frame


# -- display and governance lookups (used by render.py) --------------------------------------------------------------


def is_fraction(kpi_id: str) -> bool:
    """Growth and bias are fractions (0.05 = 5%); every other % KPI is already in percentage points."""
    return _entries()[kpi_id]["derived"] in ("growth", "bias")


def display(kpi_id: str, value: float) -> str:
    """A value as a person reads it: 'EUR 12.3 M', '5.1%', '4.2 weeks', '1,234'."""
    e = _entries()[kpi_id]
    if pd.isna(value):
        return "n/a"
    if is_fraction(kpi_id):
        return f"{value * 100:.1f}%"
    unit = e["unit"]
    if unit == "EUR":
        return f"EUR {value:,.1f} M"
    if unit == "%":
        return f"{value:.1f}%"
    if unit == "weeks":
        return f"{value:.1f} weeks"
    return f"{value:,.0f}"


@lru_cache(maxsize=1)
def _governance_tables() -> dict[str, pd.DataFrame]:
    return pd.read_excel(DEFAULT_XLSX, sheet_name=["Semantic_Models", "Owners"])


def model_info(model_id: str) -> dict:
    """Source model of a spec: endorsement and refresh status for the governance footer."""
    models = _governance_tables()["Semantic_Models"].set_index("model_id")
    return models.loc[model_id].to_dict() if model_id in models.index else {}


def owner_info(owner_id: str) -> dict:
    owners = _governance_tables()["Owners"].set_index("owner_id")
    return owners.loc[owner_id].to_dict() if owner_id in owners.index else {}
