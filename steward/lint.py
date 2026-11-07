"""W6 lint gate: rules on the DashboardSpec itself (BUILD_PLAN 5.2). Pure code, no LLM.

`lint(spec, catalog)` returns exactly one LintResult per rule, in a fixed order (pass / warn / block);
a rule that does not apply passes with "not applicable". `can_approve(spec)` is false when any result blocks.
Exceptions to RULE-002 are recorded as spec.provenance["exception:<KPI id>"] = reason.
"""

from __future__ import annotations

from .catalog import Catalog
from .linking import asset_metric_ids, kpi_index, kpi_jaccard
from .models import Artifact
from .spec import DashboardSpec, LintResult, Measure

RULES = (
    "RULE-001",
    "RULE-002",
    "RULE-003",
    "RULE-004",
    "RULE-005",
    "RULE-006",
    "RULE-007",
    "RULE-008",
    "FOCUS",
    "DATA",
)

REUSE_JACCARD = (
    0.6  # RULE-001: canonical-metric overlap (variants count as their metric) that makes an existing asset a substitute
)
MAX_VISUALS_PER_PAGE = 7
MAX_PAGES = 2
MAX_CARDS = 4
LOW_USE_USERS = 10  # RULE-006: average monthly unique users below this = low use
HIGH_REACH_USERS = 50
HIGH_REACH_WORDS = ("executive", "leadership", "board", "all ", "global", "company")
TRUSTED = {"certified", "promoted"}
_STATUS_ORDER = {"pass": 0, "warn": 1, "block": 2}


def lint(spec: DashboardSpec, catalog: Catalog) -> list[LintResult]:
    checks = {
        "RULE-001": _rule_001,
        "RULE-002": _rule_002,
        "RULE-003": _rule_003,
        "RULE-004": _rule_004,
        "RULE-005": _rule_005,
        "RULE-006": _rule_006,
        "RULE-007": _rule_007,
        "RULE-008": _rule_008,
        "FOCUS": _focus,
        "DATA": _data,
    }
    return [checks[rule](spec, catalog) for rule in RULES]


def can_approve(spec: DashboardSpec) -> bool:
    """False as soon as one lint result blocks. The spec must have been linted (spec.lint filled)."""
    return bool(spec.lint) and all(r.status != "block" for r in spec.lint)


def worst(results: list[LintResult]) -> str:
    return max((r.status for r in results), key=_STATUS_ORDER.__getitem__, default="pass")


# ---------------------------------------------------------------- helpers


def _result(rule: str, problems: list[tuple[str, str, list[str]]], ok: str) -> LintResult:
    """problems = [(status, message, record_ids)]. The worst status wins; all messages are kept."""
    if not problems:
        return LintResult(rule_id=rule, status="pass", message=ok)
    status = max((p[0] for p in problems), key=_STATUS_ORDER.__getitem__)
    ids = sorted({i for _, _, rec in problems for i in rec})
    return LintResult(rule_id=rule, status=status, message=" ".join(p[1] for p in problems), record_ids=ids)


def _canonical_ids(catalog: Catalog) -> set[str]:
    return set(kpi_index(catalog)[0])


def _spec_kpis(spec: DashboardSpec, catalog: Catalog) -> set[str]:
    return (set(spec.kpi_ids) | {m.kpi_id for m in spec.measures if m.kpi_id}) & _canonical_ids(catalog)


def _scope(filters: dict[str, str], catalog: Catalog) -> tuple[str, str]:
    """(product id, market id); empty string = All Pharma / Global. Product names ("Nubeqa") are mapped to ids ("P-NUB")."""
    product = filters.get("product", "")
    dimension = catalog.dimensions.get("product")
    if dimension:
        product = next((v.id for v in dimension.values if product.lower() in {v.id.lower(), v.label.lower()}), product)
    market = filters.get("market", "")
    return product, "" if market.lower() == "global" else market


def _avg_users(asset: Artifact) -> float:
    return sum(u.unique_users for u in asset.usage) / len(asset.usage) if asset.usage else 0.0


def _substitutes(spec: DashboardSpec, catalog: Catalog) -> list[tuple[Artifact, float]]:
    """Active assets on the same product + market scope whose canonical KPIs overlap the spec's by Jaccard >= 0.6."""
    canonical = kpi_index(catalog)[0]
    wanted = {
        canonical[k] for k in _spec_kpis(spec, catalog)
    }  # metric ids: a variant KPI on an asset still makes it a substitute
    scope = _scope(spec.filters, catalog)
    found = []
    for asset in catalog.active_artifacts():
        if _scope(asset.filters, catalog) != scope or asset.id in spec.base_asset_ids:
            continue
        score = kpi_jaccard(wanted, asset_metric_ids(asset, catalog))
        if wanted and score >= REUSE_JACCARD:
            found.append((asset, round(score, 2)))
    return sorted(found, key=lambda x: -x[1])


def _model_asset(spec: DashboardSpec, catalog: Catalog) -> Artifact | None:
    return next(
        (a for a in catalog.active_artifacts() if spec.source_model_id and a.model_id == spec.source_model_id), None
    )


# ---------------------------------------------------------------- rules


def _rule_001(spec: DashboardSpec, catalog: Catalog) -> LintResult:
    """Reuse before build: a CREATE is blocked while a substitute asset exists."""
    if spec.change_type != "create":
        return _result("RULE-001", [], "Not applicable: this spec reuses or changes an existing asset.")
    subs = _substitutes(spec, catalog)
    if not subs:
        return _result(
            "RULE-001",
            [],
            "No existing asset on this scope covers the KPIs (Jaccard < 0.6): a new dashboard is justified.",
        )
    asset, score = subs[0]
    return _result(
        "RULE-001",
        [
            (
                "block",
                f'{asset.id} "{asset.title}" already covers {score:.0%} of these KPIs on the same scope: reuse or extend it.',
                [a.id for a, _ in subs],
            )
        ],
        "",
    )


def _rule_002(spec: DashboardSpec, catalog: Catalog) -> LintResult:
    """Every measure must be a canonical KPI; a variant needs a written exception."""
    canonical = _canonical_ids(catalog)
    variants = kpi_index(catalog)[1]
    problems = []
    for m in spec.measures:
        if m.kpi_id in canonical and m.definition_status == "canonical":
            continue
        reason = spec.provenance.get(f"exception:{m.kpi_id}", "").strip()
        label = f"{m.name} ({m.kpi_id or 'no KPI id'})"
        if m.kpi_id in variants:
            official = next((k for k, mid in kpi_index(catalog)[0].items() if mid == variants[m.kpi_id][0]), "?")
            hint = f" Use {official} instead."
        else:
            hint = ""
        if reason:
            problems.append(("warn", f"{label} is not canonical; exception recorded: {reason}.", [m.kpi_id]))
        else:
            problems.append(
                (
                    "block",
                    f"{label} is not a canonical approved KPI and has no exception reason.{hint}",
                    [m.kpi_id] if m.kpi_id else [],
                )
            )
    return _result("RULE-002", problems, "Every measure is a canonical approved KPI.")


def _rule_003(spec: DashboardSpec, catalog: Catalog) -> LintResult:
    if not spec.owner_id:
        return _result(
            "RULE-003", [("block", "No owner is set: every dashboard needs an accountable, active owner.", [])], ""
        )
    holders = [a for a in catalog.artifacts.values() if a.owner_id == spec.owner_id]
    if not holders:
        return _result(
            "RULE-003",
            [("warn", f"Owner {spec.owner_id} is set but cannot be checked against the data pack.", [spec.owner_id])],
            "",
        )
    if holders[0].owner_status != "active":
        return _result(
            "RULE-003",
            [
                (
                    "block",
                    f"Owner {spec.owner_id} is {holders[0].owner_status or 'unknown'}: assign an active owner.",
                    [spec.owner_id],
                )
            ],
            "",
        )
    return _result("RULE-003", [], f"Owner {spec.owner_id} is active.")


def _rule_004(spec: DashboardSpec, catalog: Catalog) -> LintResult:
    """Lineage: a source model must be named; a consolidation lists the downstream impact of each retirement."""
    problems = []
    if not spec.source_model_id:
        problems.append(("block", "No source model is set: lineage is required.", []))
    if spec.change_type == "consolidate":
        merged = {i for c in spec.changes if c.kind == "merge_from" for i in c.record_ids}
        for asset_id in spec.base_asset_ids[1:]:  # base_asset_ids[0] is the keeper
            asset = catalog.artifacts.get(asset_id)
            missing = [d for d in (asset.downstream_ids if asset else []) if d not in merged]
            if missing:
                problems.append(
                    (
                        "block",
                        f"Retiring {asset_id} affects {', '.join(missing)}: list the downstream impact.",
                        [asset_id, *missing],
                    )
                )
    return _result(
        "RULE-004", problems, f"Source model {spec.source_model_id} is set and the lineage impact is covered."
    )


def _rule_005(spec: DashboardSpec, catalog: Catalog) -> LintResult:
    """High reach needs trust: a failed refresh blocks, a warning warns, an unendorsed model behind a wide audience warns."""
    holder = _model_asset(spec, catalog)
    if holder is None:
        return _result("RULE-005", [], "Not applicable: no governed source model to check.")
    problems = []
    if holder.refresh_status == "failed":
        problems.append(("block", f"Model {spec.source_model_id} failed its last refresh.", [spec.source_model_id]))
    elif holder.refresh_status == "warning":
        problems.append(("warn", f"Model {spec.source_model_id} refresh has a warning.", [spec.source_model_id]))
    audience = f" {spec.audience.lower()} "
    bases = [catalog.artifacts[i] for i in spec.base_asset_ids if i in catalog.artifacts]
    high_reach = any(w in audience for w in HIGH_REACH_WORDS) or any(_avg_users(b) >= HIGH_REACH_USERS for b in bases)
    if high_reach and holder.model_endorsement not in TRUSTED:
        problems.append(
            (
                "warn",
                f"High reach but model {spec.source_model_id} is not certified or promoted.",
                [spec.source_model_id],
            )
        )
    return _result("RULE-005", problems, "The source model is healthy and trusted enough for the audience.")


def _rule_006(spec: DashboardSpec, catalog: Catalog) -> LintResult:
    """Do not migrate waste: a migration carries canonical KPIs only, merges duplicates first, never copies low use 1:1."""
    if spec.change_type != "migrate":
        return _result("RULE-006", [], "Not applicable: not a migration.")
    problems = []
    canonical = _canonical_ids(catalog)
    off = [m.kpi_id for m in spec.measures if m.kpi_id not in canonical]
    if off:
        problems.append(("block", f"A migration may carry canonical KPIs only; found {', '.join(off)}.", off))
    for base_id in spec.base_asset_ids:
        base = catalog.artifacts.get(base_id)
        if base and _avg_users(base) < LOW_USE_USERS:
            problems.append(
                (
                    "block",
                    f"{base_id} is low use ({_avg_users(base):.0f} users/month): retire it, do not recreate it 1:1.",
                    [base_id],
                )
            )
    merged = {i for c in spec.changes if c.kind == "merge_from" for i in c.record_ids}
    dupes = [a.id for a, _ in _substitutes(spec, catalog) if a.platform == "Tableau" and a.id not in merged]
    if dupes:
        problems.append(("block", f"Duplicates of the migrated asset are not merged first: {', '.join(dupes)}.", dupes))
    return _result("RULE-006", problems, "The migration is canonical, merged and not a low-use copy.")


def _rule_007(spec: DashboardSpec, catalog: Catalog) -> LintResult:
    """AI-ready semantics: visuals bound to measures with expressions, month axis on trends, business names."""
    by_name = {m.name: m for m in spec.measures}
    problems = []
    for page in spec.pages:
        for v in page.visuals:
            for name in v.measures:
                m = by_name.get(name)
                if m is None:
                    problems.append(("warn", f'Visual "{v.title}" uses "{name}", which is not a defined measure.', []))
                elif m.feasible and not (m.expression or m.source):
                    problems.append(("warn", f'Measure "{name}" has no expression or source binding.', [m.kpi_id]))
            if v.type == "line" and v.dimension != "month":
                problems.append(("warn", f'Trend "{v.title}" should use the month axis, not {v.dimension!r}.', []))
            if "KPI-" in v.title or "_" in v.title:
                problems.append(
                    (
                        "warn",
                        f'Title "{v.title}" shows a technical name; use business language (ids go in the footer).',
                        [],
                    )
                )
    return _result(
        "RULE-007",
        problems,
        "Every visual is bound to a defined measure, trends use the month axis, titles are in business language.",
    )


def _rule_008(spec: DashboardSpec, catalog: Catalog) -> LintResult:
    bare = [c for c in spec.changes if not c.record_ids]
    problems = [("block", f'Change "{c.kind}: {c.detail}" cites no record ids.', []) for c in bare]
    return _result("RULE-008", problems, "Every change cites record ids.")


def _focus(spec: DashboardSpec, catalog: Catalog) -> LintResult:
    problems = []
    if len(spec.pages) > MAX_PAGES:
        problems.append(("warn", f"{len(spec.pages)} pages; the limit is {MAX_PAGES}.", []))
    for page in spec.pages:
        if len(page.visuals) > MAX_VISUALS_PER_PAGE:
            problems.append(
                (
                    "warn",
                    f'Page "{page.name}" has {len(page.visuals)} visuals; the limit is {MAX_VISUALS_PER_PAGE}.',
                    [],
                )
            )
        cards = sum(v.type == "card" for v in page.visuals)
        if cards > MAX_CARDS:
            problems.append(("warn", f'Page "{page.name}" has {cards} KPI cards; the limit is {MAX_CARDS}.', []))
    return _result("FOCUS", problems, "At most 2 pages, 7 visuals per page and 4 KPI cards.")


def _data(spec: DashboardSpec, catalog: Catalog) -> LintResult:
    """An infeasible measure is only ever a labelled gap: no expression, a reason, and no chart that would draw numbers."""
    gaps: dict[str, Measure] = {m.name: m for m in spec.measures if not m.feasible}
    problems = []
    for m in gaps.values():
        if not m.gap_reason.strip():
            problems.append(("block", f'Gap "{m.name}" has no reason; say why there is no governed data.', [m.kpi_id]))
        if m.expression.strip():
            problems.append(
                ("block", f'Gap "{m.name}" carries an expression and could show invented numbers.', [m.kpi_id])
            )
    for page in spec.pages:
        for v in page.visuals:
            if v.type != "card":
                used = [n for n in v.measures if n in gaps]
                if used:
                    problems.append(
                        (
                            "block",
                            f'Visual "{v.title}" would draw numbers for the gap {", ".join(used)}; show it as a gap card.',
                            [],
                        )
                    )
    return _result("DATA", problems, "Every infeasible measure is shown only as a labelled gap.")
