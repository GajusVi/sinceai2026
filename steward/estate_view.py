"""Builder health view, data side (DECISION T3.2, Martynas): the estate grouped by ROOT CAUSE, not asset by asset.

The audit's finding: 69 reports sit on failed refresh but only 14 semantic models are failing; 65 reports have an
inactive owner but only 13 people left. "134 problem reports" is not a plan a builder can finish; "14 model fixes and 13
reassignments" is. This module turns the catalog into that list. No UI here: Donatas / Gajus place it in the builder tab.

Plain code, one pass over the catalog (O(n), unlike the duplicate scan): the same input gives the same output.
Counts are facts from the data pack, never LLM text. Provisional assets (DECISION C4) are not part of the estate.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from pydantic import BaseModel, Field

from .catalog import Catalog
from .decision import lifecycle
from .models import Artifact, ArtifactStatus


class ModelFix(BaseModel):
    """One failing semantic model and every report it takes down."""

    model_id: str
    assets: list[str]
    certified: list[str] = Field(default_factory=list)  # certified reports that are not refreshing
    owner_ids: list[str] = Field(default_factory=list)  # who owns the reports on it (who to tell)


class OwnerFix(BaseModel):
    """One inactive owner (or the nobody owner) and every report that needs a new owner."""

    owner_id: str  # "" = reports with no owner at all
    name: str = ""
    role: str = ""
    scope: str = ""
    assets: list[str]
    certified: list[str] = Field(default_factory=list)
    tier: str  # a = same role + scope successor, b = same role other scope (steward picks), c = role vacant, none = no owner
    successor: str = ""  # the proposed person for tier a, else ""
    candidates: list[str] = Field(default_factory=list)


class RepairAction(BaseModel):
    kind: str  # FIX_REFRESH | REASSIGN_OWNER
    target: str  # model id or owner id ("" = reports without any owner)
    heals: list[str]  # reports that are healthy again if this one action is done
    certified_heals: int = 0
    text: str = ""


class EstateView(BaseModel):
    total: int
    failed_refresh_assets: int
    failing_models: int
    inactive_owner_assets: int
    inactive_owners: int
    no_owner_assets: int
    certified_on_failed_refresh: list[str]  # the headline: a certificate on a report whose data is not refreshing
    model_fixes: list[ModelFix]
    owner_fixes: list[OwnerFix]
    actions: list[RepairAction]  # ranked: most reports healed first


class MyAsset(BaseModel):
    id: str
    title: str
    endorsement: str
    issues: list[str]  # FAILED_REFRESH | REFRESH_WARNING | RETIRE_CANDIDATE | LOW_USAGE | NO_ACTIVE_OWNER
    users_last_3m: float | None = None  # average monthly unique users, last 3 months with data
    users_before: float | None = None  # the 3 months before
    trend: str = "n/a"  # up | down | flat | n/a


class MyAssets(BaseModel):
    owner_id: str
    total: int
    needing_attention: int
    assets: list[MyAsset]  # worst first


def _estate(catalog: Catalog) -> list[Artifact]:
    return [a for a in catalog.active_artifacts() if a.status != ArtifactStatus.PROVISIONAL]


def _tier(asset: Artifact, ref: lifecycle.Reference) -> tuple[str, str, list[str]]:
    """BUILD_PLAN 11.2 successor order, same as lifecycle.reassign_owner but as data."""
    if not asset.owner_id:
        return "none", "", []
    same = [c for c in asset.successor_candidates if ref.owners[c]["scope"] == asset.owner_scope]
    other = [c for c in asset.successor_candidates if c not in same]
    if same:
        return "a", same[0], same
    if other:
        return "b", "", other
    return "c", "", []


def estate_view(catalog: Catalog) -> EstateView:
    ref = lifecycle.reference()
    estate = _estate(catalog)

    by_model: dict[str, list[Artifact]] = defaultdict(list)
    by_owner: dict[str, list[Artifact]] = defaultdict(list)
    for a in estate:
        if a.refresh_status == "failed" and a.model_id:
            by_model[a.model_id].append(a)
        if a.owner_status != "active":  # inactive, or missing altogether
            by_owner[a.owner_id].append(a)

    model_fixes = [
        ModelFix(
            model_id=m,
            assets=sorted(a.id for a in assets),
            certified=sorted(a.id for a in assets if a.endorsement == "certified"),
            owner_ids=sorted({a.owner_id for a in assets if a.owner_id}),
        )
        for m, assets in by_model.items()
    ]
    model_fixes.sort(key=lambda f: (-len(f.assets), -len(f.certified), f.model_id))

    owner_fixes = []
    for owner_id, assets in by_owner.items():
        tier, successor, candidates = _tier(assets[0], ref)
        person = ref.owners.get(owner_id, {})
        owner_fixes.append(
            OwnerFix(
                owner_id=owner_id,
                name=str(person.get("owner_name", "")),
                role=str(person.get("role", "")),
                scope=str(person.get("scope", "")),
                assets=sorted(a.id for a in assets),
                certified=sorted(a.id for a in assets if a.endorsement == "certified"),
                tier=tier,
                successor=successor,
                candidates=candidates,
            )
        )
    owner_fixes.sort(key=lambda f: (-len(f.assets), -len(f.certified), f.owner_id))

    actions = [
        RepairAction(
            kind="FIX_REFRESH",
            target=f.model_id,
            heals=f.assets,
            certified_heals=len(f.certified),
            text=f"Fix the refresh of {f.model_id}: {len(f.assets)} reports work again"
            + (f", {len(f.certified)} of them certified" if f.certified else ""),
        )
        for f in model_fixes
    ] + [
        RepairAction(
            kind="REASSIGN_OWNER",
            target=f.owner_id,
            heals=f.assets,
            certified_heals=len(f.certified),
            text=_owner_text(f),
        )
        for f in owner_fixes
    ]
    actions.sort(key=lambda x: (-len(x.heals), -x.certified_heals, x.kind, x.target))

    certified_broken = sorted(a.id for a in estate if a.refresh_status == "failed" and a.endorsement == "certified")
    return EstateView(
        total=len(estate),
        failed_refresh_assets=sum(len(f.assets) for f in model_fixes),
        failing_models=len(model_fixes),
        inactive_owner_assets=sum(len(f.assets) for f in owner_fixes if f.owner_id),
        inactive_owners=sum(1 for f in owner_fixes if f.owner_id),
        no_owner_assets=sum(len(f.assets) for f in owner_fixes if not f.owner_id),
        certified_on_failed_refresh=certified_broken,
        model_fixes=model_fixes,
        owner_fixes=owner_fixes,
        actions=actions,
    )


def _owner_text(f: OwnerFix) -> str:
    who = f"{f.owner_id} ({f.name}, {f.role})" if f.owner_id else "reports with no owner"
    n = f"{len(f.assets)} reports"
    if f.tier == "a":
        return f"Reassign {who}: {n}; proposed successor {f.successor}, same role and scope (they must accept)"
    if f.tier == "b":
        return f"Reassign {who}: {n}; same role in another scope, the steward picks ({len(f.candidates)} candidates)"
    if f.tier == "c":
        return f"Reassign {who}: {n}; the role is vacant, escalate to the BI Platform Owner"
    return f"Assign an owner to {n} that have none: escalate to the BI Platform Owner"


# -- "my assets" ---------------------------------------------------------------------------------------------------


def _users(a: Artifact, months: int = 3) -> tuple[float | None, float | None]:
    usage = sorted(a.usage, key=lambda u: u.month)
    if not usage:
        return None, None
    last, before = usage[-months:], usage[-2 * months : -months]
    mean = lambda rows: round(sum(u.unique_users for u in rows) / len(rows), 1) if rows else None  # noqa: E731
    return mean(last), mean(before)


def my_assets(catalog: Catalog, owner_id: str, retire_ids: frozenset[str] | set[str] = frozenset()) -> MyAssets:
    """Panu point 6, builder side: the assets one person owns, the unhealthy ones first, each with its reasons.
    `retire_ids` = lifecycle.estate(...).retire keys, passed in so this stays O(n) (the estate scan is the slow part)."""
    mine = [a for a in _estate(catalog) if a.owner_id == owner_id]
    rows = []
    for a in mine:
        last, before = _users(a)
        trend = "n/a"
        if last is not None and before is not None:
            trend = "up" if last > before * 1.1 else "down" if last < before * 0.9 else "flat"
        issues = []
        if a.refresh_status == "failed":
            issues.append("FAILED_REFRESH")
        elif a.refresh_status == "warning":
            issues.append("REFRESH_WARNING")
        if a.id in retire_ids:
            issues.append("RETIRE_CANDIDATE")
        elif last is not None and last < 10:
            issues.append("LOW_USAGE")
        if a.owner_status != "active":
            issues.append("NO_ACTIVE_OWNER")
        rows.append(
            MyAsset(
                id=a.id, title=a.title, endorsement=a.endorsement, issues=issues,
                users_last_3m=last, users_before=before, trend=trend,
            )
        )
    severity = {"FAILED_REFRESH": 0, "NO_ACTIVE_OWNER": 1, "RETIRE_CANDIDATE": 2, "REFRESH_WARNING": 3, "LOW_USAGE": 4}
    rows.sort(key=lambda r: (min((severity[i] for i in r.issues), default=9), -len(r.issues), r.id))
    return MyAssets(
        owner_id=owner_id, total=len(rows), needing_attention=sum(1 for r in rows if r.issues), assets=rows
    )
