"""The worker's fast path (Panu Q&A: the production floor must get info and decide fast; they never build).

No interview. A worker gets: suggested prompts for their department, a short free-text chat, and "Other" (request
another department's data at the same plant). Every answer is REUSE ONLY: the best existing report the worker may see
(steward/auth.can_see), shown as it is on the worker's plant. What no existing report covers is listed, with one
button to request it from the BI team. Nothing here creates a dashboard or a KPI.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .auth import User, can_see
from .intent import Intent
from .linking import artifact_covered_metrics
from .models import Candidate, Decision, StewardResult, Verdict

SUPPLY = ["on_time_in_full", "inventory_coverage", "demand_forecast_accuracy"]


@dataclass(frozen=True)
class Prompt:
    label: str
    metric_ids: tuple[str, ...] = ()
    not_governed: str = ""  # a need with no governed KPI yet: answered honestly, request only


# Suggested prompts by department. Data-pack KPIs where they exist; equipment and quality numbers are not governed in
# the pack, so those prompts say so and lead to a request (built anyway, as Gajus asked, Sat 16:20).
PROMPTS: dict[str, list[Prompt]] = {
    "Warehouse Ops": [
        Prompt("Is supply safe at my plant?", tuple(SUPPLY)),
        Prompt("Weeks of stock on hand", ("inventory_coverage",)),
        Prompt("Deliveries on time and complete", ("on_time_in_full",)),
    ],
    "Equipment Ops": [
        Prompt("Units shipped this month", ("units_shipped",)),
        Prompt("Line downtime", not_governed="line downtime"),
        Prompt("Equipment effectiveness (OEE)", not_governed="equipment effectiveness (OEE)"),
    ],
    "Quality Ops": [
        Prompt("Batch yield", not_governed="batch yield"),
        Prompt("Deliveries on time and complete", ("on_time_in_full",)),
        Prompt("Forecast accuracy", ("demand_forecast_accuracy",)),
    ],
    "Supply Planning": [
        Prompt("Forecast accuracy", ("demand_forecast_accuracy",)),
        Prompt("Forecast bias", ("demand_forecast_bias",)),
        Prompt("Weeks of stock on hand", ("inventory_coverage",)),
    ],
}
DEPARTMENTS = list(PROMPTS)

# "Other": what a worker typically needs from another department (mini grill, step 2). "Something else" = free text.
NEEDS: dict[str, list[str]] = {
    "Warehouse Ops": ["Stock on hand by product", "Inbound and outbound deliveries", "Shipping delays"],
    "Equipment Ops": ["Line downtime", "Planned maintenance windows", "Equipment effectiveness (OEE)"],
    "Quality Ops": ["Batch release status", "Batch yield", "Deviations open"],
    "Supply Planning": ["Demand forecast by product", "Production plan for the next weeks", "Stock-out risks"],
}
# Free-text chat, offline: plain floor words -> governed metric ids (the LLM interviewer is tried first) and the
# needs that have no governed KPI in the data pack (answered honestly, request only).
WORDS: dict[str, tuple[str, ...]] = {
    "stock": ("inventory_coverage",), "inventory": ("inventory_coverage",), "cover": ("inventory_coverage",),
    "on time": ("on_time_in_full",), "deliver": ("on_time_in_full",), "otif": ("on_time_in_full",),
    "late": ("on_time_in_full",), "forecast": ("demand_forecast_accuracy",), "shipped": ("units_shipped",),
    "units": ("units_shipped",), "volume": ("units_shipped",), "supply": tuple(SUPPLY),
}
NOT_GOVERNED_WORDS = {
    "downtime": "line downtime", "oee": "equipment effectiveness (OEE)",
    "effectiveness": "equipment effectiveness (OEE)",
    "yield": "batch yield", "cost per unit": "cost per unit", "lead time": "supplier lead times",
    "deviation": "quality deviations", "maintenance": "planned maintenance", "release": "batch release status",
}


def words_to_metrics(text: str) -> tuple[list[str], str]:
    """(metric ids, not-governed need) found in plain words. Both empty = not understood."""
    low = text.lower()
    metrics: list[str] = []
    for word, ids in WORDS.items():
        if re.search(rf"\b{word}", low):  # word start: "late" must not match "related"
            metrics += [m for m in ids if m not in metrics]
    need = next((v for k, v in NOT_GOVERNED_WORDS.items() if re.search(rf"\b{k}", low)), "")
    return metrics, need


CADENCES = ["Every shift", "Weekly", "One-off check"]


@dataclass
class WorkerAnswer:
    result: StewardResult | None = None  # the existing report, rendered on the worker's plant (REUSE spec)
    covered: list[str] = field(default_factory=list)  # metric ids the report answers
    missing: list[str] = field(default_factory=list)  # metric ids no visible report answers
    not_governed: str = ""
    refused: str = ""  # plain-words reason when the question is out of the worker's scope


def other_plant(user: User, sites: list[str]) -> str:
    """A plant the user may not open (empty if none). Workers never; management only its own or granted plants."""
    if user.role == "builder":
        return ""
    return next((s for s in sites if s not in user.plants), "")


def refusal(user: User, site: str) -> str:
    if user.role == "worker":
        return f"You are signed in for {user.plant}. {site}'s numbers come through your manager."
    return f"{site} is not in your access yet. Ask the BI team for it (a builder grants access)."


def reuse_only(steward, user: User, metric_ids: list[str], text: str, supply) -> WorkerAnswer:
    """The best existing report this user may see that carries the asked numbers, on the user's plant. No build."""
    if not metric_ids:
        return WorkerAnswer()
    intent = Intent(
        metric_ids=list(metric_ids), sites=[user.plant], text=text, decision_supported="monitor",
        confidence={"metric_ids": 1.0, "sites": 1.0, "decision_supported": 1.0},
    )
    hits = steward.search.search(intent.to_parsed_question(), limit=len(steward.catalog.artifacts))
    best, covered = None, []
    for rank, hit in enumerate(hits):  # most covered numbers, then certified, Power BI, most used, search order
        a = hit.artifact
        if not can_see(user, a.product_scope, a.market_scope, supply):
            continue
        has = [m for m in metric_ids if m in artifact_covered_metrics(a, steward.catalog)]  # canonical KPI ids only
        key = (len(has), a.certified, a.platform != "Tableau", a.views_30d, -rank)
        if has and (best is None or key > best[0]):
            best, covered = (key, hit), has
    if best is None:
        return WorkerAnswer(missing=list(metric_ids))
    hit = best[1]
    candidate = Candidate(
        artifact=hit.artifact, search_score=hit.score, coverage=len(covered) / len(metric_ids), trust=0.0,
        covered=covered, gaps=[], compatible=True, score=hit.score,
    )
    missing = [m for m in metric_ids if m not in covered]
    shown = intent.model_copy(update={"metric_ids": covered})
    result = StewardResult(
        question=shown.to_parsed_question(), decision=Decision(verdict=Verdict.REUSE, best=candidate),
        explanation="", as_of=steward.as_of,
    )
    return WorkerAnswer(result=steward.build(result, shown), covered=covered, missing=missing)


# -- requests from the floor (Other / missing numbers) -> the builders' queue --------------------------------------
LOG_FILE = "floor_requests.jsonl"  # in the steward data dir, beside the journal; a demo store, not a ticket system


def request_entry(user: User, kind: str, need: str, department: str = "", cadence: str = "") -> dict:
    """kind: 'access' (another department's data, same plant) or 'report' (a number no visible report has)."""
    return {
        "kind": kind, "who": user.label, "username": user.username, "plant": user.plant,
        "from_department": user.department or "", "department": department, "need": need, "cadence": cadence,
        "status": "open", "at": datetime.now().isoformat(timespec="seconds"),
    }


def log_request(data_dir: Path, entry: dict, status: str, actor: str) -> None:
    """Append-only trail: who asked for what, who granted or declined it, when."""
    data_dir.mkdir(parents=True, exist_ok=True)
    row = {**entry, "status": status, "decided_by": actor if status != "open" else "",
           "logged_at": datetime.now().isoformat(timespec="seconds")}
    with (data_dir / LOG_FILE).open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def read_log(data_dir: Path) -> list[dict]:
    path = data_dir / LOG_FILE
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
