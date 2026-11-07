"""Lifecycle flags on the recommended report (BUILD_PLAN section 11.2): FIX_REFRESH, REASSIGN_OWNER, RETIRE and the
Migration_Backlog evidence behind MIGRATE. Every flag comes with Evidence that cites record ids (RULE-008).

Data-pack assets only: the sample catalog has none of these fields, so its goldens are untouched.

RETIRE is a recommendation, never an action (owner/steward approves, reversible for 30 days). It needs ALL of:
old enough to judge, low use relative to comparable assets AND in each of the last months, nobody depends on it quietly,
and a reason beyond low use (a more trusted duplicate, or no active owner). A report that carries a high-criticality
KPI is never recommended for retirement: it goes to HUMAN_REVIEW instead. Thresholds: steward/config.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache

import numpy as np

from ..catalog import Catalog
from ..config import (
    CONSOLIDATE_JACCARD,
    RETIRE_BOTTOM_SHARE,
    RETIRE_MAX_USERS_RECENT,
    RETIRE_MIN_AGE_MONTHS,
    RETIRE_RECENT_MONTHS,
)
from ..linking import canonical_kpis, kpi_index, kpi_jaccard
from ..models import Artifact, Decision, Evidence
from .signals import trust

BI_PLATFORM_OWNER = "BI Platform Owner"


@dataclass(frozen=True)
class Reference:
    """Sheets the artifacts do not carry: who the people are, which KPIs are critical, workspace scope, backlog."""

    owners: dict[str, dict]
    high_kpis: frozenset[str]
    workspace_scope: dict[str, str]
    backlog: dict[str, dict]


@lru_cache(maxsize=1)
def reference() -> Reference:
    import pandas as pd

    from ..datapack import DEFAULT_XLSX

    sheets = pd.read_excel(DEFAULT_XLSX, sheet_name=["Owners", "KPI_Catalog", "Workspaces", "Migration_Backlog"])
    owners = {r["owner_id"]: r for r in sheets["Owners"].to_dict("records")}
    kpis = sheets["KPI_Catalog"]
    return Reference(
        owners=owners,
        high_kpis=frozenset(kpis[kpis.business_criticality == "high"].kpi_id),
        workspace_scope=dict(zip(sheets["Workspaces"].workspace_id, sheets["Workspaces"].scope, strict=True)),
        backlog={r["source_asset_id"]: r for r in sheets["Migration_Backlog"].to_dict("records")},
    )


def _who(ref: Reference, owner_id: str) -> str:
    o = ref.owners.get(owner_id)
    return f"{owner_id} ({o['owner_name']}, {o['role']})" if o else owner_id


def _month_index(d: date) -> int:
    return d.year * 12 + d.month


# -- FIX_REFRESH ------------------------------------------------------------------------------------------------


def fix_refresh(artifact: Artifact) -> list[Evidence]:
    if artifact.refresh_status not in ("failed", "warning"):
        return []
    claim = (
        f"The semantic model {artifact.model_id} behind {artifact.id} has refresh status '{artifact.refresh_status}'"
    )
    if artifact.refresh_status == "failed":
        claim += ": its numbers may be stale, fix the refresh before anyone relies on this report (RULE-005)"
        if artifact.endorsement == "certified":
            claim += ". The report is certified on a model whose refresh failed"
    return [
        Evidence(
            claim=claim,
            rule_id="RULE-005",
            record_ids=[artifact.model_id, artifact.id],
            value=artifact.refresh_status,
            severity="warning",
        )
    ]


# -- REASSIGN_OWNER ---------------------------------------------------------------------------------------------


def reassign_owner(artifact: Artifact, ref: Reference) -> list[Evidence]:
    """Owner inactive or missing: propose a successor in the BUILD_PLAN 11.2 order. Never assigned automatically."""
    if artifact.owner_status == "active":
        return []
    ids = [artifact.id]
    if artifact.owner_id:
        ids.append(artifact.owner_id)
        what = f"The owner {_who(ref, artifact.owner_id)} is inactive"
    else:
        what = "The report has no owner at all"
    same_scope = [c for c in artifact.successor_candidates if ref.owners[c]["scope"] == artifact.owner_scope]
    other_scope = [c for c in artifact.successor_candidates if c not in same_scope]
    if same_scope:
        proposal = same_scope[0]
        claim = f"{what}. Proposed successor: {_who(ref, proposal)}, same role and scope. They must accept (RULE-003)"
        ids.append(proposal)
    elif other_scope:
        shown = ", ".join(_who(ref, c) for c in other_scope[:3])
        claim = f"{what}. Same role, other scope, the steward picks: {shown} (RULE-003)"
        ids += other_scope[:3]
    else:
        platform_owner = _platform_owner(artifact, ref)
        role = ref.owners[artifact.owner_id]["role"] if artifact.owner_id in ref.owners else "none"
        who = _who(ref, platform_owner) if platform_owner else "the BI Platform Owner"
        claim = f"{what}; the role ({role}) is vacant. Escalate to {who} and report it as an estate finding (RULE-003)"
        if platform_owner:
            ids.append(platform_owner)
    status = artifact.owner_status or "missing"
    return [Evidence(claim=claim, rule_id="RULE-003", record_ids=ids, value=status, severity="warning")]


def _platform_owner(artifact: Artifact, ref: Reference) -> str:
    """The active BI Platform Owner, preferably one whose scope matches the workspace."""
    active = [o for o in ref.owners.values() if o["role"] == BI_PLATFORM_OWNER and o["status"] == "active"]
    scope = ref.workspace_scope.get(artifact.workspace_id)
    match = [o for o in active if o["scope"] == scope] or active
    return match[0]["owner_id"] if match else ""


# -- MIGRATE (evidence only: the flag itself is set by the engine) ------------------------------------------------


def migrate_evidence(artifact: Artifact, ref: Reference) -> list[Evidence]:
    """A Tableau report: say what the backlog CLAIMS and whether real use justifies a copy at all (RULE-006)."""
    if artifact.platform != "Tableau":
        return []
    out: list[Evidence] = []
    avg = avg_users(artifact)
    if avg is not None and avg < RETIRE_MAX_USERS_RECENT:
        out.append(
            Evidence(
                claim=(
                    f"{artifact.id} has only {avg:.1f} users a month: do not migrate it 1:1, "
                    "rebuild only what is used (RULE-006)"
                ),
                rule_id="RULE-006",
                record_ids=[artifact.id],
                value=f"{avg:.1f} users/month",
                severity="warning",
            )
        )
    row = ref.backlog.get(artifact.id)
    if row:
        out.append(
            Evidence(
                claim=(
                    f"Migration backlog claims '{row['recommended_path_candidate']}' to model "
                    f"{row['candidate_target_model_id']} (complexity {row['complexity']}, status {row['status']}). "
                    "A claim, not a fact: check the target model's "
                    "refresh before using it (RULE-006)"
                ),
                rule_id="RULE-006",
                record_ids=[artifact.id, str(row["candidate_target_model_id"])],
                severity="info",
            )
        )
    return out


# -- RETIRE -----------------------------------------------------------------------------------------------------


def avg_users(artifact: Artifact) -> float | None:
    """Average monthly unique users since creation (usage rows before creation are already dropped)."""
    if not artifact.usage:
        return None
    return sum(u.unique_users for u in artifact.usage) / len(artifact.usage)


def bottom_cuts(catalog: Catalog) -> dict[str, float]:
    """Per asset type: the average-users value below which an asset is in the bottom RETIRE_BOTTOM_SHARE."""
    by_type: dict[str, list[float]] = {}
    for a in catalog.active_artifacts():
        if (avg := avg_users(a)) is not None:
            by_type.setdefault(a.type, []).append(avg)
    return {t: float(np.percentile(v, RETIRE_BOTTOM_SHARE * 100)) for t, v in by_type.items()}


@dataclass
class RetireAssessment:
    artifact_id: str
    checks: dict[str, bool] = field(default_factory=dict)  # old_enough, low_use, quiet, reason, not_critical
    facts: dict[str, str] = field(default_factory=dict)
    duplicate_of: str = ""
    critical_kpis: list[str] = field(default_factory=list)
    downstream: list[str] = field(default_factory=list)

    @property
    def retire(self) -> bool:
        return all(self.checks.get(k) for k in ("old_enough", "low_use", "quiet", "reason", "not_critical"))

    @property
    def human_review(self) -> bool:
        """Everything holds except that a high-criticality KPI is involved."""
        return not self.checks.get("not_critical", True) and all(
            self.checks.get(k) for k in ("old_enough", "low_use", "quiet", "reason")
        )


def assess_retire(
    artifact: Artifact, catalog: Catalog, as_of: date, ref: Reference, cuts: dict[str, float] | None = None
) -> RetireAssessment:
    cuts = cuts if cuts is not None else bottom_cuts(catalog)
    result = RetireAssessment(artifact.id)
    created = artifact.created_date
    result.checks["old_enough"] = bool(created) and _month_index(as_of) - _month_index(created) >= RETIRE_MIN_AGE_MONTHS

    window = {_month_index(as_of) - i for i in range(1, RETIRE_RECENT_MONTHS + 1)}
    recent = [u for u in artifact.usage if _month_index(u.month) in window]
    avg = avg_users(artifact)
    cut = cuts.get(artifact.type)
    quiet_months = bool(recent) and all(u.unique_users < RETIRE_MAX_USERS_RECENT for u in recent)
    result.checks["low_use"] = avg is not None and cut is not None and avg <= cut and quiet_months
    if avg is not None:
        result.facts["avg"] = f"{avg:.1f}"
    if cut is not None:
        result.facts["cut"] = f"{cut:.1f}"

    result.downstream = [d for d in artifact.downstream_ids if d.startswith("AST-")]
    subscriptions = sum(u.subscriptions for u in recent)
    result.facts["subscriptions"] = str(subscriptions)
    result.checks["quiet"] = bool(recent) and subscriptions == 0 and not result.downstream

    result.critical_kpis = sorted(set(artifact.kpi_ids) & ref.high_kpis)
    result.checks["not_critical"] = not result.critical_kpis

    result.duplicate_of = _more_trusted_duplicate(artifact, catalog, as_of)
    result.checks["reason"] = bool(result.duplicate_of) or artifact.owner_status != "active"
    return result


def _more_trusted_duplicate(artifact: Artifact, catalog: Catalog, as_of: date) -> str:
    mine = canonical_kpis(artifact, catalog)
    if not mine:
        return ""
    my_trust = trust(artifact, as_of)
    best, best_trust = "", my_trust
    for other in catalog.active_artifacts():
        if other.id == artifact.id or other.product_scope != artifact.product_scope:
            continue
        if kpi_jaccard(mine, canonical_kpis(other, catalog)) < CONSOLIDATE_JACCARD:
            continue
        t = trust(other, as_of)
        if t > best_trust:
            best, best_trust = other.id, t
    return best


def retire_evidence(artifact: Artifact, a: RetireAssessment, catalog: Catalog, as_of: date) -> list[Evidence]:
    ids = [artifact.id]
    if a.human_review:
        return [
            Evidence(
                claim=(
                    f"{artifact.id} looks unused and redundant, but it carries high-criticality KPI "
                    f"{', '.join(a.critical_kpis[:3])}: a person reviews it, it is not recommended for retirement"
                ),
                rule_id="RETIRE",
                record_ids=ids + a.critical_kpis[:3],
                severity="warning",
            )
        ]
    out = [
        Evidence(
            claim=(
                f"{artifact.id} is a retire candidate: {a.facts['avg']} users a month since {artifact.created_date}, "
                "in the bottom "
                f"{RETIRE_BOTTOM_SHARE:.0%} of {artifact.type} assets (cut {a.facts['cut']}), and under "
                f"{RETIRE_MAX_USERS_RECENT} users in each of the last {RETIRE_RECENT_MONTHS} months"
            ),
            rule_id="RETIRE",
            record_ids=ids,
            value=f"{a.facts['avg']} users/month",
            severity="warning",
        )
    ]
    if a.duplicate_of:
        other = catalog.artifact(a.duplicate_of)
        out.append(
            Evidence(
                claim=(
                    f"Reason: a more trusted duplicate exists, {other.id} '{other.title}' "
                    f"(trust {trust(other, as_of):.2f} vs {trust(artifact, as_of):.2f}, same product scope, "
                    "KPI overlap >= "
                    f"{CONSOLIDATE_JACCARD:.0%})"
                ),
                rule_id="RULE-001",
                record_ids=[artifact.id, other.id],
                severity="info",
            )
        )
    else:
        out.append(
            Evidence(
                claim=f"Reason: no active owner ({artifact.owner_status or 'none'})",
                rule_id="RULE-003",
                record_ids=ids + ([artifact.owner_id] if artifact.owner_id else []),
                severity="info",
            )
        )
    out.append(
        Evidence(
            claim=(
                "Impact (RULE-004): no downstream asset depends on it and it has 0 subscriptions in the last "
                f"{RETIRE_RECENT_MONTHS} months. Never automatic: the owner or steward approves, "
                "archived and reversible for 30 days"
            ),
            rule_id="RULE-004",
            record_ids=ids,
            severity="info",
        )
    )
    return out


# -- entry point ------------------------------------------------------------------------------------------------


def add_lifecycle(decision: Decision, catalog: Catalog, as_of: date) -> Decision:
    """Adds the flags and their evidence for the recommended report. No-op on the sample catalog and without a best."""
    best = decision.best.artifact if decision.best else None
    if best is None or not best.platform or not kpi_index(catalog)[0]:
        return decision
    ref = reference()
    flags: list[str] = []
    evidence: list[Evidence] = []

    if found := fix_refresh(best):
        flags.append("FIX_REFRESH")
        evidence += found
    if found := reassign_owner(best, ref):
        flags.append("REASSIGN_OWNER")
        evidence += found
    if best.platform == "Tableau":
        flags.append("MIGRATE")
        evidence += migrate_evidence(best, ref)
    assessment = assess_retire(best, catalog, as_of, ref)
    if assessment.retire:
        flags.append("RETIRE")
        evidence += retire_evidence(best, assessment, catalog, as_of)
    elif assessment.human_review:
        flags.append("HUMAN_REVIEW")
        evidence += retire_evidence(best, assessment, catalog, as_of)

    decision.flags = list(dict.fromkeys([*decision.flags, *flags]))
    decision.evidence = [*decision.evidence, *evidence]
    return decision
