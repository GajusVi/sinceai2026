"""Spec builder (W5): a verdict becomes a DashboardSpec with the template layout of BUILD_PLAN 5.1.

REUSE / RESCUE / EXTEND / MIGRATE / CONSOLIDATE / CREATE (G9); CLARIFY and
NOT_FEASIBLE build nothing (None). Plain code, same input -> same output. The LLM layout proposal (G10) comes later and
must stay inside the menus defined here.
"""

from __future__ import annotations

import hashlib
import json
import logging
from functools import lru_cache

import pandas as pd

from . import semantic
from .catalog import Catalog
from .datapack import ALL_PHARMA, DEFAULT_XLSX, GLOBAL
from .intent import Intent
from .layout import Layouter, Option
from .linking import artifact_variants, asset_metric_ids
from .models import Artifact, Decision, Verdict
from .semantic import ASSET_LEVEL_KPIS as ASSET_LEVEL
from .semantic import Feasibility, grain_of, measure, star_schema
from .spec import DashboardSpec, Measure, Page, SpecChange, Visual

logger = logging.getLogger(__name__)

MAX_CARDS = 4
# Exception tables the template can add: kpi_id -> (threshold, title template). A fixed menu, not a free choice.
EXCEPTIONS = {
    "KPI-042": (10.0, "{who} more than 10% off forecast"),
    "KPI-020": (90.0, "{who} below 90% on-time in-full"),
    "KPI-016": (4.0, "{who} with less than 4 weeks of stock"),
}
COMPARED_TO_FORECAST = {"KPI-001", "KPI-042"}
DIMENSION_WORD = {"market": "country", "product": "product", "region": "region"}
DIMENSION_PLURAL = {"market": "countries", "product": "products", "region": "regions"}


def spec_hash(spec: DashboardSpec) -> str:
    """Stable id of what the human approves: everything except lint results and the hash itself."""
    body = json.dumps(spec.model_dump(exclude={"lint", "provenance"}), sort_keys=True, default=str)
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def build_spec(
    decision: Decision,
    intent: Intent,
    catalog: Catalog,
    feasibility: Feasibility,
    layouter: Layouter | None = None,
) -> DashboardSpec | None:
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
    if verdict == Verdict.CONSOLIDATE and best:
        spec = _consolidate(best, decision, intent, catalog, measures, layouter)
    elif verdict in (Verdict.REUSE, Verdict.EXTEND) and best:
        spec = spec_from_asset(best, decision, intent, catalog, measures, layouter)
    else:
        spec = _create(decision, intent, catalog, measures, layouter)
    if layouter is not None:
        spec.provenance.update(layouter.info)  # layout_source llm | template (+ model, prompt, role); not in the hash
    return spec


def _change_type(asset: Artifact, decision: Decision) -> str:
    """reuse | rescue (reuse, owner gone) | migrate (Tableau base: rebuilt in Power BI) | extend."""
    if asset.platform == "Tableau":
        return "migrate"  # Tableau is never reused as is (decision B); the engine flags MIGRATE
    if decision.verdict == Verdict.REUSE:
        return "rescue" if asset.owner_status != "active" else "reuse"
    return "extend"


def _owner_change(asset: Artifact) -> tuple[str, SpecChange]:
    """RESCUE: the first same-role successor (data pack Owners sheet) becomes the proposed owner; a human confirms."""
    successors = asset.successor_candidates
    owner = successors[0] if successors else ""
    detail = (
        f"Owner {asset.owner_id or '(none)'} is not active; first same-role successor {owner} (must accept)"
        if owner
        else "No active owner and no same-role successor: a human must assign one"
    )
    return owner, SpecChange(
        kind="assign_owner", detail=detail, record_ids=[r for r in (asset.id, asset.owner_id, owner) if r]
    )


def spec_from_asset(
    asset: Artifact,
    decision: Decision,
    intent: Intent,
    catalog: Catalog,
    measures: list[Measure],
    layouter: Layouter | None = None,
) -> DashboardSpec:
    """REUSE: the asset as it is. RESCUE: the same, with a successor owner. EXTEND: its next version. MIGRATE: a
    rationalised Power BI rebuild of a Tableau asset (canonical KPIs only, RULE-006), never a 1:1 copy."""
    change_type = _change_type(asset, decision)
    reuse = change_type == "reuse"
    dimension = _dimension(intent)
    page = _page(measures, intent, catalog, dimension, layouter)
    changes: list[SpecChange] = []
    owner = asset.owner_id
    model_id = asset.model_id
    if change_type in ("extend", "migrate"):
        changes = _changes(asset, measures, page, dimension, catalog)
    if asset.owner_status != "active" and not reuse:
        owner, change = _owner_change(asset)
        changes.append(change)
    if change_type == "migrate":
        model = best_model(intent)
        model_id = model["model_id"]
        changes.append(
            SpecChange(
                kind="migrate_platform",
                detail=f"Rebuild {asset.id} in Power BI on {model_id} with canonical KPIs only; the Tableau workbook "
                "is retired after sign-off, not copied 1:1 (RULE-006)",
                record_ids=[asset.id, model_id, *[m.kpi_id for m in measures]],
            )
        )
    missing = [m.name for m in measures if m.kpi_id not in asset.kpi_ids]
    rationale = {
        "reuse": f'"{asset.title}" ({asset.id}) already answers the question; shown on governed data.',
        "rescue": f'"{asset.title}" ({asset.id}) already answers the question, but its owner is not active: '
        "reuse it once a successor accepts.",
        "migrate": f'"{asset.title}" ({asset.id}) is a Tableau asset: rebuilt in Power BI on canonical KPIs, '
        f"adding {', '.join(missing) or 'nothing'}.",
        "extend": f'"{asset.title}" ({asset.id}) is the closest asset; it lacks {", ".join(missing) or "nothing"}.',
    }[change_type]
    spec = _spec(
        intent,
        catalog,
        measures,
        page,
        owner=owner,
        model_id=model_id,
        base=[asset.id],
        version=asset.version if reuse else asset.version + 1,
        changes=changes,
        verdict=decision.verdict.value,
        change_type=change_type,
        rationale=rationale,
    )
    return spec


def _consolidate(
    keeper: Artifact,
    decision: Decision,
    intent: Intent,
    catalog: Catalog,
    measures: list[Measure],
    layouter: Layouter | None = None,
) -> DashboardSpec:
    """CONSOLIDATE: the keeper's next version carries the union of the cluster's canonical KPIs (up to MAX_CARDS,
    requested ones first); every other member is merged in and retired, with its downstream impact (RULE-001, -004)."""
    in_cluster = {i for e in decision.evidence if e.rule_id == "RULE-001" for i in e.record_ids}
    others = [c.artifact for c in decision.alternatives if c.artifact.id in in_cluster and c.artifact.id != keeper.id]
    members = [keeper, *others]
    measures = _union(measures, members, catalog)
    spec = spec_from_asset(keeper, decision, intent, catalog, measures, layouter)
    merges = [
        SpecChange(
            kind="merge_from",
            detail=f"Merge {a.id} into {keeper.id}, then retire {a.id}"
            + (
                f"; downstream impact: {', '.join(a.downstream_ids)} repoint to {keeper.id}" if a.downstream_ids else ""
            ),
            record_ids=[a.id, keeper.id, *a.downstream_ids],
        )
        for a in others
    ]
    names = ", ".join(a.id for a in others) or "no other member"
    spec = spec.model_copy(
        update={
            "change_type": "consolidate",
            "base_asset_ids": [keeper.id, *[a.id for a in others]],
            "changes": spec.changes + merges,
            "rationale": f'Duplicates of "{keeper.title}" ({keeper.id}, the most trusted) exist: {names}. '
            "One dashboard carries their canonical KPIs; the others are retired after sign-off."
            + (
                " The keeper is Tableau: the merged version is a Power BI rebuild."
                if keeper.platform == "Tableau"
                else ""
            ),
        }
    )
    spec.provenance["spec_hash"] = spec_hash(spec)
    return spec


def _union(measures: list[Measure], members: list[Artifact], catalog: Catalog) -> list[Measure]:
    """Requested measures first, then canonical KPIs the members carry and the semantic layer binds, up to MAX_CARDS."""
    have = {m.kpi_id for m in measures}
    bindable = {m.kpi_id: m for m in semantic.all_measures() if m.feasible}
    out = list(measures)
    for asset in members:
        for metric_id in sorted(asset_metric_ids(asset, catalog)):
            kpi = catalog.metrics[metric_id].kpi_id if metric_id in catalog.metrics else ""
            if kpi in bindable and kpi not in have and len(out) < MAX_CARDS:
                out.append(bindable[kpi])
                have.add(kpi)
    return out


def _create(
    decision: Decision, intent: Intent, catalog: Catalog, measures: list[Measure], layouter: Layouter | None = None
) -> DashboardSpec:
    model = best_model(intent)
    dimension = _dimension(intent)
    page = _page(measures, intent, catalog, dimension, layouter)
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


def _card(m: Measure, who: str, intent: Intent) -> Visual:
    return Visual(
        type="card",
        title=f"{who} {m.name.lower()}",
        measures=[m.name],
        comparison=_comparison(m, intent),
        purpose=f"Headline: {m.name}" if m.feasible else f"Governed KPI without source data: {m.name}",
    )


def _line(m: Measure, who: str) -> Visual:
    vs = "forecast" if m.kpi_id in COMPARED_TO_FORECAST else None
    return Visual(
        type="line",
        title=f"{who} {m.name.lower()} by month" + (" vs forecast" if vs else ""),
        measures=[m.name],
        dimension="month",
        comparison=vs,
        purpose="See when it moved",
    )


def _bar(m: Measure, who: str, dimension: str) -> Visual:
    return Visual(
        type="bar",
        title=f"{who} {m.name.lower()}, by {DIMENSION_WORD[dimension]}",
        measures=[m.name],
        dimension=dimension,
        purpose=f"Which {DIMENSION_PLURAL[dimension]} drive it",
    )


def _table(m: Measure, dimension: str) -> Visual:
    threshold, title = EXCEPTIONS[m.kpi_id]
    plural = {"market": "Countries", "product": "Products", "region": "Regions"}[dimension]
    return Visual(
        type="table",
        title=title.format(who=plural),
        measures=[m.name],
        dimension=dimension,
        threshold=threshold,
        purpose=f"Which {DIMENSION_PLURAL[dimension]} to look at first",
    )


def _menu(measures: list[Measure], intent: Intent, catalog: Catalog, dimension: str) -> list[Option]:
    """Every visual the rules allow for these measures (the layout menu): cards (gaps last), a trend per monthly
    measure, a breakdown per measure that has one, an exceptions table per measure with a governed threshold. The
    template layout is the first of each kind; the LLM layout (layout.py) chooses and orders from this menu only."""
    who = _scope_label(intent, catalog)
    buildable = [m for m in measures if m.feasible]
    out = [Option(f"card:{m.kpi_id}", _card(m, who, intent), m.kpi_id, m.feasible) for m in buildable]
    out += [Option(f"card:{m.kpi_id}", _card(m, who, intent), m.kpi_id, False) for m in measures if not m.feasible]
    out += [Option(f"line:{m.kpi_id}", _line(m, who), m.kpi_id) for m in buildable if grain_of(m.kpi_id) == "month"]
    out += [
        Option(f"bar:{m.kpi_id}", _bar(m, who, dimension), m.kpi_id)
        for m in buildable
        if m.kpi_id not in ASSET_LEVEL
    ]
    out += [Option(f"table:{m.kpi_id}", _table(m, dimension), m.kpi_id) for m in buildable if m.kpi_id in EXCEPTIONS]
    return out


def _legal(options: list[Option], measures: list[Measure], intent: Intent) -> list[Option]:
    """Drop the menu entries the data in this scope cannot show (semantic.check_visual: a trend needs enough months,
    a ranking 3..20 members of its dimension). Cards always stay (a gap is a labelled gap card). If the data cannot be
    profiled (sample catalog, missing frames) the menu is returned unchanged."""
    try:
        from .semantic import check_visual, profile

        profiles = profile(measures, None, _filters(intent))
    except Exception as exc:  # noqa: BLE001 - profiling is an extra check, never a reason to fail the build
        logger.debug("layout profile skipped: %s", exc)
        return options
    return [
        o
        for o in options
        if o.visual.type == "card" or not check_visual(profiles, o.visual.type, o.visual.measures, o.visual.dimension)
    ]


def _page(
    measures: list[Measure], intent: Intent, catalog: Catalog, dimension: str, layouter: Layouter | None = None
) -> Page:
    """The template layout of BUILD_PLAN 5.1 (<= 4 cards, 1 trend, 1 breakdown, 1 exceptions table). With a `layouter`
    the order, the density and the choice from the menu follow the viewer (layout.py); without one: template."""
    options = _legal(_menu(measures, intent, catalog, dimension), measures, intent)
    first = lambda kind: next((o.visual for o in options if o.visual.type == kind), None)  # noqa: E731
    cards = [o.visual for o in options if o.visual.type == "card"][:MAX_CARDS]
    visuals = cards + [v for v in (first("line"), first("bar"), first("table")) if v]
    who = _scope_label(intent, catalog)
    template = Page(name="What needs attention", purpose=f"Where {who} needs action", visuals=visuals)
    if layouter is None:
        return template
    return layouter.arrange(options, template, intent)


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
