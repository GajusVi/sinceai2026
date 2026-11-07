"""Loads the Bayer data pack (xlsx) into 360 Artifacts. BUILD_PLAN D1.

One row of Analytics_Assets becomes one Artifact, joined with owners, KPIs, usage, semantic model, lineage,
governance signals and data-quality findings. Columns the pack itself says we must not trust (lifecycle_status,
estimated_audience) are kept as "claimed" and never used for decisions.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import pandas as pd

from .models import Artifact, ArtifactMetric, ArtifactStatus, DimensionDefinition, MetricDefinition, UsageMonth

ORIGINAL_XLSX = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "bayer"
    / "Bayer_Pharmaceuticals_SinceAI_2026_FINAL_Builder_Data_Pack.xlsx"
)
# STEWARD_DATAPACK_XLSX switches every loader to another pack with the same structure (tools/make_large_pack.py).
# Unset = the original pack: tests, golden verdicts and the pitch numbers are tied to it.
DEFAULT_XLSX = Path(os.environ.get("STEWARD_DATAPACK_XLSX") or ORIGINAL_XLSX).resolve()
ALL_PHARMA = "All Pharma"
GLOBAL = "Global"
_NAME_SUFFIX = re.compile(r" - (EMEA|US|Global)$")


def load_artifacts(xlsx: Path = DEFAULT_XLSX) -> list[Artifact]:
    sheets = pd.read_excel(xlsx, sheet_name=None)
    return _build(sheets)


def _build(s: dict[str, pd.DataFrame]) -> list[Artifact]:
    products = dict(zip(s["Products"].product_name, s["Products"].product_id))
    region_of = dict(zip(s["Markets"].market_id, s["Markets"].region))
    owners = s["Owners"].set_index("owner_id").to_dict("index")
    kpis = s["KPI_Catalog"].set_index("kpi_id").to_dict("index")
    models = s["Semantic_Models"].set_index("model_id").to_dict("index")
    successors = _successors(s["Owners"])

    kpi_ids = _group(s["Asset_KPI_Map"], "asset_id", "kpi_id")
    usage = {aid: g for aid, g in s["Asset_Usage"].groupby("asset_id")}
    signals = _group_rows(s["Governance_Signals"], "asset_id", lambda r: f"{r.signal_code}:{r.severity}:{r.status}")
    dq_assets = _group(s["Data_Quality"][s["Data_Quality"].sheet == "Analytics_Assets"], "record_id", "issue_id")
    dq_models = _group(s["Data_Quality"][s["Data_Quality"].sheet == "Semantic_Models"], "record_id", "issue_id")
    upstream, downstream = _lineage(s["Lineage_Edges"])

    artifacts = []
    for row in s["Analytics_Assets"].itertuples(index=False):
        aid = row.asset_id
        created = _date(row.created_date)
        modified = _date(row.last_modified)
        owner_id = _text(row.owner_id)
        owner = owners.get(owner_id) if owner_id else None
        model = models.get(row.model_id, {})
        kpi_list = kpi_ids.get(aid, [])

        months, early = _usage_months(usage.get(aid), created)
        data_quality = list(dq_assets.get(aid, [])) + list(dq_models.get(row.model_id, []))
        if early:
            data_quality.append("USAGE_BEFORE_CREATED")
        if modified < created:
            data_quality.append("MODIFIED_BEFORE_CREATED")
        mismatch = _name_scope_mismatch(row.asset_name, row.market_scope, region_of)
        if mismatch:
            data_quality.append(mismatch)

        artifacts.append(
            Artifact(
                id=aid,
                title=row.asset_name,
                type=row.asset_type,
                description=f"{row.asset_type} on {row.platform}: {row.product_scope}, {row.market_scope}",
                domain=_domain(kpi_list, kpis),
                metrics=[ArtifactMetric(label=kpis[k]["kpi_name"], formula=k) for k in kpi_list if k in kpis],
                dimensions=_dimensions(row.product_scope, row.market_scope),
                filters=_filters(row.product_scope, row.market_scope, products),
                owner=owner["owner_name"] if owner else "",
                owner_active=bool(owner and owner["status"] == "active"),
                certified=row.endorsement == "certified",
                last_refreshed=modified,  # = last_modified: the pack has no refresh timestamp for assets
                views_30d=months[-1].views
                if months
                else 0,  # latest month in the pack (Oct 2026), not a rolling 30 days
                family_id=aid,
                status=ArtifactStatus.ACTIVE,  # lifecycle_status is claimed, not trusted: see lifecycle_claimed
                source_tables=[row.model_id],
                platform=row.platform,
                workspace_id=row.workspace_id,
                model_id=row.model_id,
                product_scope=row.product_scope,
                market_scope=row.market_scope,
                kpi_ids=kpi_list,
                endorsement=row.endorsement,
                lifecycle_claimed=row.lifecycle_status,
                created_date=created,
                owner_id=owner_id,
                owner_role=owner["role"] if owner else "",
                owner_scope=owner["scope"] if owner else "",
                owner_status=owner["status"] if owner else "",
                successor_candidates=successors.get(owner_id, []) if owner and owner["status"] != "active" else [],
                usage=months,
                refresh_status=model.get("refresh_status", ""),
                model_endorsement=model.get("endorsement", ""),
                signals=signals.get(aid, []),
                data_quality=data_quality,
                upstream_ids=upstream.get(aid, []),
                downstream_ids=downstream.get(aid, []),
            )
        )
    return artifacts


def _successors(owners: pd.DataFrame) -> dict[str, list[str]]:
    """For each owner: active people with the same role and scope first, then same role other scope. Never themselves."""
    active = owners[owners.status == "active"]
    result = {}
    for o in owners.itertuples(index=False):
        same_role = active[(active.role == o.role) & (active.owner_id != o.owner_id)]
        first = same_role[same_role.scope == o.scope].owner_id.tolist()
        rest = same_role[same_role.scope != o.scope].owner_id.tolist()
        result[o.owner_id] = first + rest
    return result


def _usage_months(rows: pd.DataFrame | None, created: date) -> tuple[list[UsageMonth], int]:
    """Only months from the creation month on count; earlier rows are reported as a data-quality finding."""
    if rows is None:
        return [], 0
    start = created.replace(day=1)
    months, early = [], 0
    for r in rows.sort_values("month").itertuples(index=False):
        month = _date(r.month)
        if month < start:
            early += 1
            continue
        months.append(
            UsageMonth(
                month=month,
                views=int(r.views),
                unique_users=int(r.unique_users),
                exports=int(r.exports),
                subscriptions=int(r.subscriptions),
                query_errors=int(r.query_errors),
            )
        )
    return months, early


def _lineage(edges: pd.DataFrame) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """upstream[x] = what x is built on; downstream[x] = what is built on x. An edge points source -> target."""
    up: dict[str, list[str]] = {}
    down: dict[str, list[str]] = {}
    for e in edges.itertuples(index=False):
        up.setdefault(e.target_id, []).append(e.source_id)
        down.setdefault(e.source_id, []).append(e.target_id)
    return up, down


def _name_scope_mismatch(name: str, market_scope: str, region_of: dict[str, str]) -> str | None:
    """Trap 18: scope comes from market_scope, never from the name. A suffix that disagrees is a DQ finding."""
    m = _NAME_SUFFIX.search(name)
    if not m:
        return None
    suffix = m.group(1)
    if suffix == market_scope or (suffix == "EMEA" and region_of.get(market_scope) == "EMEA"):
        return None
    return f"NAME_SCOPE_MISMATCH:name={suffix},scope={market_scope}"


def _dimensions(product_scope: str, market_scope: str) -> list[str]:
    """Breakdowns the asset can show: All Pharma -> by product, Global -> by market and region. Always monthly."""
    dims = ["month"]
    if product_scope == ALL_PHARMA:
        dims.append("product")
    if market_scope == GLOBAL:
        dims += ["market", "region"]
    return dims


def _filters(product_scope: str, market_scope: str, product_ids: dict[str, str]) -> dict[str, str]:
    filters = {}
    if product_scope != ALL_PHARMA:
        filters["product"] = product_ids.get(product_scope, product_scope)
    if market_scope != GLOBAL:
        filters["market"] = market_scope
    return filters


def _domain(kpi_list: list[str], kpis: dict) -> str:
    return next((kpis[k]["domain"] for k in kpi_list if k in kpis), "")


def _group(df: pd.DataFrame, key: str, value: str) -> dict[str, list[str]]:
    return _group_rows(df, key, lambda r: getattr(r, value))


def _group_rows(df: pd.DataFrame, key: str, fn) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in df.itertuples(index=False):
        out.setdefault(getattr(r, key), []).append(fn(r))
    return out


def _date(value) -> date:
    return pd.Timestamp(value).date()


def _text(value) -> str:
    return "" if pd.isna(value) else str(value)


def load_catalog(xlsx: Path, catalog_dir: Path, data_dir: Path | None = None):
    """Catalog from the data pack plus catalog_dir/metrics.json + dimensions.json (catalog/bayer/) and approved changes."""
    from .catalog import Catalog, apply_changes, read_json

    artifacts = apply_changes(load_artifacts(xlsx), data_dir)
    metrics = [MetricDefinition.model_validate(m) for m in read_json(catalog_dir / "metrics.json")]
    dimensions = [DimensionDefinition.model_validate(d) for d in read_json(catalog_dir / "dimensions.json")]
    return Catalog(artifacts, metrics, dimensions)
