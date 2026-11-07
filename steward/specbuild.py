"""Spec builder (W5): a verdict becomes a DashboardSpec with the template layout of BUILD_PLAN 5.1.

REUSE / EXTEND / CREATE tonight; CONSOLIDATE falls back to EXTEND on the keeper until Saturday (G9); CLARIFY and
NOT_FEASIBLE build nothing (None). Plain code, same input -> same output. The LLM layout proposal (G10) comes later and
must stay inside the menus defined here.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache

import pandas as pd

from . import semantic
from .catalog import Catalog
from .datapack import ALL_PHARMA, DEFAULT_XLSX, GLOBAL
from .intent import Intent
from .linking import artifact_variants
from .models import Artifact, Decision, Verdict
from .semantic import ASSET_LEVEL_KPIS as ASSET_LEVEL
from .semantic import Feasibility, grain_of, measure, star_schema
from .spec import DashboardSpec, Measure, Page, SpecChange, Visual

MAX_CARDS = 4
# Exception tables the template can add: kpi_id -> (threshold, title template). A fixed menu, not a free choice.
EXCEPTIONS = {
    "KPI-042": (10.0, "{who} more than 10% off forecast"),
    "KPI-020": (90.0, "{who} below 90% on-time in-full"),
    "KPI-016": (4.0, "{who} with less than 4 weeks of stock"),
}
COMPARED_TO_FORECAST = {"KPI-001", "KPI-042"}
DIMENSION_WORD = {"market": "country", "product": "product", "region": "region"}


def spec_hash(spec: DashboardSpec) -> str:
    """Stable id of what the human approves: everything except lint results and the hash itself."""
    body = json.dumps(spec.model_dump(exclude={"lint", "provenance"}), sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def build_spec(decision: Decision, intent: Intent, catalog: Catalog, feasibility: Feasibility) -> DashboardSpec | None:
    verdict = decision.verdict
    if verdict in (Verdict.CLARIFY, Verdict.NOT_FEASIBLE):
        return None
    measures = feasibility.buildable + feasibility.gaps
    if not measures:
        return None
    wanted = {m.kpi_id for m in measures}
    if "KPI-042" in wanted and "KPI-001" not in wanted:
        measures = [measure("KPI-001")] + measures  # a forecast variance is read against net sales: context measure
    best = decision.best.artifact if decision.best else None
    if verdict in (Verdict.REUSE, Verdict.EXTEND, Verdict.CONSOLIDATE) and best:
        return spec_from_asset(best, decision, intent, catalog, measures)
    return _create(decision, intent, catalog, measures)


def spec_from_asset(
    asset: Artifact, decision: Decision, intent: Intent, catalog: Catalog, measures: list[Measure]
) -> DashboardSpec:
    """REUSE: the asset as it is, shown on governed data. EXTEND (and CONSOLIDATE for now): its next version."""
    reuse = decision.verdict == Verdict.REUSE
    dimension = _dimension(intent)
    page = _page(measures, intent, catalog, dimension)
    changes: list[SpecChange] = []
    owner = asset.owner_id
    if not reuse:
        changes = _changes(asset, measures, page, dimension, catalog)
        if asset.owner_status != "active":
            successors = asset.successor_candidates
            owner = successors[0] if successors else ""
            detail = (
                f"Owner {asset.owner_id or '(none)'} is not active; first same-role successor {owner} (must accept)"
                if owner
                else "No active owner and no same-role successor: a human must assign one"
            )
            changes.append(
                SpecChange(
                    kind="assign_owner", detail=detail, record_ids=[r for r in (asset.id, asset.owner_id, owner) if r]
                )
            )
    missing = [m.name for m in measures if m.kpi_id not in asset.kpi_ids]
    spec = _spec(
        intent,
        catalog,
        measures,
        page,
        owner=owner,
        model_id=asset.model_id,
        base=[asset.id],
        version=asset.version if reuse else asset.version + 1,
        changes=changes,
        verdict=decision.verdict.value,
        change_type="reuse" if reuse else "extend",
        rationale=(
            f'"{asset.title}" ({asset.id}) already answers the question; shown on governed data.'
            if reuse
            else f'"{asset.title}" ({asset.id}) is the closest asset; it lacks {", ".join(missing) or "nothing"}.'
            + (
                " CONSOLIDATE is drafted as an extension of the keeper for now."
                if decision.verdict == Verdict.CONSOLIDATE
                else ""
            )
        ),
    )
    return spec


def _create(decision: Decision, intent: Intent, catalog: Catalog, measures: list[Measure]) -> DashboardSpec:
    model = best_model(intent)
    dimension = _dimension(intent)
    page = _page(measures, intent, catalog, dimension)
    change = SpecChange(
        kind="assign_owner",
        detail=f"Default owner = owner {model['owner_id']} of the source model {model['model_id']} (editable)",
        record_ids=[model["model_id"], model["owner_id"]],
    )
    return _spec(
        intent,
        catalog,
        measures,
        page,
        owner=model["owner_id"],
        model_id=model["model_id"],
        base=[],
        version=1,
        changes=[change],
        verdict=decision.verdict.value,
        change_type="create",
        rationale=(
            f"No compatible asset exists. Built on the governed model {model['model_id']} "
            f"({model['endorsement']}, refresh {model['refresh_status']}, scope {model['product_scope']})."
        ),
    )


# -- layout (BUILD_PLAN 5.1) ---------------------------------------------------------------------------------------


def _dimension(intent: Intent) -> str:
    """Breakdown dimension: product if several products are asked, else market (several markets, a region, global).
    A site supplies several medicines: break it down by product."""
    if len(intent.products) > 1 or (intent.sites and len(intent.products) != 1):
        return "product"
    if len(intent.markets) == 1 and intent.markets[0] != GLOBAL and len(intent.products) != 1:
        return "product"
    return "market"


def _scope_label(intent: Intent, catalog: Catalog) -> str:
    names = [p for p in intent.products if p != ALL_PHARMA]
    who = names[0] if len(names) == 1 else "Bayer Pharma"
    if len(intent.sites) == 1:
        who = f"{intent.sites[0]}" + (f" {names[0]}" if len(names) == 1 else "")
    if len(intent.markets) == 1 and intent.markets[0] != GLOBAL:
        who += f" in {catalog.dimension_value_label('market', intent.markets[0])}"
    elif len(intent.regions) == 1:
        who += f" in {intent.regions[0]}"
    return who


def _page(measures: list[Measure], intent: Intent, catalog: Catalog, dimension: str) -> Page:
    who = _scope_label(intent, catalog)
    buildable = [m for m in measures if m.feasible]
    visuals: list[Visual] = []
    for m in (buildable + [m for m in measures if not m.feasible])[:MAX_CARDS]:
        visuals.append(
            Visual(
                type="card",
                title=f"{who} {m.name.lower()}",
                measures=[m.name],
                comparison=_comparison(m, intent),
                purpose=f"Headline: {m.name}" if m.feasible else f"Governed KPI without source data: {m.name}",
            )
        )
    trend = next((m for m in buildable if grain_of(m.kpi_id) == "month"), None)
    if trend:
        vs = "forecast" if trend.kpi_id in COMPARED_TO_FORECAST else None
        visuals.append(
            Visual(
                type="line",
                title=f"{who} {trend.name.lower()} by month" + (" vs forecast" if vs else ""),
                measures=[trend.name],
                dimension="month",
                comparison=vs,
                purpose="See when it moved",
            )
        )
    by_dim = next((m for m in buildable if m.kpi_id not in ASSET_LEVEL), None)
    if by_dim:
        visuals.append(
            Visual(
                type="bar",
                title=f"{who} {by_dim.name.lower()}, by {DIMENSION_WORD[dimension]}",
                measures=[by_dim.name],
                dimension=dimension,
                purpose=f"Which {DIMENSION_WORD[dimension]}s drive it",
            )
        )
    rule = next((m for m in buildable if m.kpi_id in EXCEPTIONS), None)
    if rule:
        threshold, title = EXCEPTIONS[rule.kpi_id]
        plural = {"market": "Countries", "product": "Products", "region": "Regions"}[dimension]
        visuals.append(
            Visual(
                type="table",
                title=title.format(who=plural),
                measures=[rule.name],
                dimension=dimension,
                threshold=threshold,
                purpose=f"Which {DIMENSION_WORD[dimension]}s to look at first",
            )
        )
    return Page(name="What needs attention", purpose=f"Where {who} needs action", visuals=visuals)


def _comparison(m: Measure, intent: Intent) -> str | None:
    if not m.feasible or grain_of(m.kpi_id) != "month":
        return None
    if m.kpi_id in COMPARED_TO_FORECAST:
        return "forecast"
    return {"forecast": "forecast", "prior": "prior_month"}.get(intent.comparison or "", "prior_month")


def _changes(
    asset: Artifact, measures: list[Measure], page: Page, dimension: str, catalog: Catalog
) -> list[SpecChange]:
    """One SpecChange per element the new version adds or swaps, each with the record ids behind it (RULE-008)."""
    out = [
        SpecChange(
            kind="add_measure",
            detail=f"Add {m.name} ({m.kpi_id}), requested and missing from {asset.id}",
            record_ids=[asset.id, m.kpi_id],
        )
        for m in measures
        if m.feasible and m.kpi_id not in asset.kpi_ids
    ]
    asked = {m.kpi_id for m in measures}
    for variant, metric_id, status in artifact_variants(asset, catalog):
        canonical = catalog.metrics[metric_id].kpi_id
        if canonical in asked:
            out.append(
                SpecChange(
                    kind="swap_variant",
                    detail=f"Replace {variant} ({status}) with the canonical {canonical}",
                    record_ids=[asset.id, variant, canonical],
                )
            )
    for m in measures:
        if not m.feasible:
            out.append(
                SpecChange(
                    kind="add_measure",
                    detail=f"{m.name} ({m.kpi_id}) is governed but has no source data: shown as a gap",
                    record_ids=[asset.id, m.kpi_id],
                )
            )
    wanted = "dim_market" if dimension == "market" else "dim_product"
    if dimension not in asset.dimensions:
        out.append(
            SpecChange(
                kind="add_breakdown",
                detail=f"Add the breakdown by {DIMENSION_WORD[dimension]}",
                record_ids=[asset.id, wanted],
            )
        )
    for visual in page.visuals:
        if visual.type == "table":
            out.append(
                SpecChange(
                    kind="add_breakdown",
                    detail=f"Add exceptions table: {visual.title.lower()}",
                    record_ids=[asset.id, *[m.kpi_id for m in measures if m.name in visual.measures]],
                )
            )
    return out


def _spec(
    intent: Intent,
    catalog: Catalog,
    measures: list[Measure],
    page: Page,
    *,
    owner: str,
    model_id: str,
    base: list[str],
    version: int,
    changes: list[SpecChange],
    verdict: str,
    change_type: str,
    rationale: str,
) -> DashboardSpec:
    tables = {m.source.split(".")[0] for m in measures if m.feasible and "." in m.source} | {"fact_pmm"}
    entities, columns, relationships = star_schema()
    keep = (tables | {"dim_product", "dim_market", "dim_month"}) & set(entities)
    who = _scope_label(intent, catalog)
    spec = DashboardSpec(
        name=f"{who}: " + ", ".join(m.name for m in measures),
        entities=[e for e in entities if e in keep],
        columns={e: c for e, c in columns.items() if e in keep},
        grain={t: "month" for t in keep if t == "fact_pmm"},
        relationships=[r for r in relationships if r.from_entity in keep and r.to_entity in keep],
        measures=measures,
        pages=[page],
        filters=_filters(intent),
        kpi_ids=[m.kpi_id for m in measures],
        source_model_id=model_id,
        owner_id=owner,
        rationale=rationale,
        verdict=verdict,
        change_type=change_type,
        base_asset_ids=base,
        version=version,
        changes=changes,
        audience=intent.audience,
        decision_supported=intent.decision_supported,
        cadence=intent.cadence or "monthly",
        provenance={"layout_source": "template", "model": "", "prompt": ""},
    )
    spec.provenance["spec_hash"] = spec_hash(spec)
    return spec


def _filters(intent: Intent) -> dict[str, str]:
    f: dict[str, str] = {}
    names = [p for p in intent.products if p != ALL_PHARMA]
    if len(names) == 1:
        f["product"] = names[0]
    if len(intent.markets) == 1 and intent.markets[0] != GLOBAL:
        f["market"] = intent.markets[0]
    if len(intent.regions) == 1:
        f["region"] = intent.regions[0]
    if len(intent.sites) == 1:
        f["site"] = intent.sites[0]
    return f


# -- CREATE: the best governed semantic model ----------------------------------------------------------------------


@lru_cache(maxsize=1)
def _models() -> pd.DataFrame:
    return pd.read_excel(DEFAULT_XLSX, sheet_name="Semantic_Models")


def best_model(intent: Intent) -> dict:
    """Power BI, certified or promoted, refresh healthy, ACTIVE owner (RULE-003 would block otherwise); then product
    scope match, region match, certified, AI-readiness."""
    models = _models()
    ok = models[
        (models.model_type == "Power BI semantic model")
        & models.endorsement.isin(["certified", "promoted"])
        & (models.refresh_status == "healthy")
    ].copy()
    names = [p for p in intent.products if p != ALL_PHARMA]
    wants_global = GLOBAL in intent.markets or (not intent.markets and not intent.regions)
    dim_market = semantic.load_frames()["dim_market"]
    region_of = dict(zip(dim_market["market_id"], dim_market["region"], strict=True))
    regions = set(intent.regions) | {region_of[m] for m in intent.markets if m in region_of}

    def rank(r) -> tuple:
        owner_ok = 0 if semantic.owner_info(r.owner_id).get("status") == "active" else 1
        product = 0 if (names and r.product_scope in names) else (1 if r.product_scope == ALL_PHARMA else 2)
        region = 0 if (wants_global and r.region_scope == GLOBAL) or r.region_scope in regions else 1
        return (
            owner_ok,
            product,
            region,
            0 if r.endorsement == "certified" else 1,
            {"good": 0, "partial": 1}.get(r.ai_readiness, 2),
            r.model_id,
        )

    ok["rank"] = ok.apply(rank, axis=1)
    top = ok.sort_values("rank").iloc[0]
    return {
        k: top[k] for k in ("model_id", "owner_id", "endorsement", "refresh_status", "product_scope", "region_scope")
    }
