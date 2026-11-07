"""The worker's fast path (Panu Q&A: the production floor must get info and decide fast; they never build).

No interview. A worker gets: suggested prompts for their department, a short free-text chat, and "Other" (request
another department's data at the same plant). Every answer is REUSE ONLY: the best existing report the worker may see
(steward/auth.can_see), shown as it is on the worker's plant. What no existing report covers is listed, with one
button to request it from the BI team. Nothing here creates a dashboard or a KPI.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .auth import User, can_see
from .intent import Intent
from .linking import artifact_covered_metrics
from .models import Candidate, Decision, StewardResult, Verdict
from .prompts import render_prompt

logger = logging.getLogger(__name__)

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
    "late": ("on_time_in_full",), "forecast": ("demand_forecast_accuracy",), "ship": ("units_shipped",),
    "units": ("units_shipped",), "volume": ("units_shipped",), "supply": tuple(SUPPLY),
    "schedule": ("on_time_in_full",), "behind": ("on_time_in_full",), "on track": ("on_time_in_full",),
}
NOT_GOVERNED_WORDS = {
    "downtime": "line downtime", "oee": "equipment effectiveness (OEE)",
    "effectiveness": "equipment effectiveness (OEE)",
    "yield": "batch yield", "cost per unit": "cost per unit", "lead time": "supplier lead times",
    "deviation": "quality deviations", "maintenance": "planned maintenance", "release": "batch release status",
    "ahead": "a shipping plan to compare against", "behind plan": "a shipping plan to compare against",
    "against plan": "a shipping plan to compare against", "vs plan": "a shipping plan to compare against",
}
# Commercial questions are not answered on the floor view (the menu holds operations KPIs only): say so honestly
# instead of offering an operations number that sounds like an answer.
_COMMERCIAL = re.compile(r"\b(sales|revenue|turnover|margin|price|pricing|gross[- ]to[- ]net|market access)\b", re.I)
_WANTS_REPORT = re.compile(r"\b(dashboards?|reports?|views?|screens?)\b", re.I)


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


_PLANT = re.compile(r"\bplant[\s-]*([abc])\b", re.I)
_CMO = re.compile(r"\b(cmo|contract manufactur\w*)\b", re.I)


def sites_named(text: str) -> list[str]:
    """Plants named in free text, without a model call ("plant b", "Plant-B", "the CMO")."""
    found = [f"Plant-{m.upper()}" for m in _PLANT.findall(text)]
    return found + (["External-CMO"] if _CMO.search(text) else [])


def refusal(user: User, site: str) -> str:
    if user.role == "worker":
        return f"You are signed in for {user.plant}. {site}'s numbers come through your manager."
    return f"{site} is not in your access yet. Ask the BI team for it (a builder grants access)."


def reuse_only(steward, user: User, metric_ids: list[str], text: str, supply, prefer: str = "") -> WorkerAnswer:
    """The best existing report this user may see that carries the asked numbers, on the user's plant. No build.
    prefer: an artifact id that wins when visible (a report the user picked)."""
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
        key = (a.id == prefer, len(has), a.certified, a.platform != "Tableau", a.views_30d, -rank)
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
    return WorkerAnswer(result=steward.build(result, shown, user), covered=covered, missing=missing)


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


# -- dynamic suggestions (chat): the AI picks single KPIs or existing reports, never a new build -------------------
MAX_PICKS = 4
MENU_REPORTS = 8


@dataclass
class Suggestion:
    id: str  # "kpi:<metric_id>" or "report:<artifact_id>"
    label: str
    why: str = ""


@dataclass
class Suggestions:
    reply: str
    items: list[Suggestion] = field(default_factory=list)
    by_ai: bool = False


# The floor works with operations numbers only: commercial KPIs (net sales, gross-to-net, market access...) are for
# management and finance, so they are not offered to workers even when a visible report carries them.
OPS_METRICS = {m for prompts in PROMPTS.values() for p in prompts for m in p.metric_ids} | set(SUPPLY)


def menu(steward, user: User, supply) -> dict[str, str]:
    """What this user can open right now: each operations KPI a visible report carries, plus the most trusted reports
    that carry one. id -> label. The AI may only pick from here (validated after the call)."""
    visible = [a for a in steward.catalog.artifacts.values() if can_see(user, a.product_scope, a.market_scope, supply)]
    ops = {a.id: artifact_covered_metrics(a, steward.catalog) & OPS_METRICS for a in visible}
    carried = set().union(*ops.values()) if ops else set()
    items = {f"kpi:{m}": steward.catalog.metrics[m].name for m in steward.catalog.metrics if m in carried}
    governed = [a for a in visible if ops[a.id]]
    top = sorted(governed, key=lambda a: (len(ops[a.id]), a.certified, a.platform != "Tableau", a.views_30d),
                 reverse=True)  # reuse first: the report that already carries most of the floor's numbers
    for a in top[:MENU_REPORTS]:
        items[f"report:{a.id}"] = f"{a.title} ({', '.join(steward.catalog.metrics[m].name for m in sorted(ops[a.id]))})"
    return items


def _on_topic(steward, items: list[Suggestion], asked: list[str]) -> list[Suggestion]:
    """Code check on the AI's picks: when the question names its numbers (stock, late deliveries, shipped...), keep
    only picks that show one of them. The model tends to pad the list (units shipped for a stock question)."""
    if not asked:
        return items
    kept = []
    for item in items:
        kind, _, key = item.id.partition(":")
        shows = {key} if kind == "kpi" else artifact_covered_metrics(steward.catalog.artifacts[key], steward.catalog)
        if shows & set(asked):
            kept.append(item)
    return kept


def suggest(steward, user: User, text: str, supply) -> Suggestions:
    """AI first (validated picks from the menu), else the offline rule: words in the question, then the department's
    usual prompts. Code rails on top: commercial questions get an honest no; picks that miss the numbers the question
    names are dropped; a question asking for a dashboard always gets the best existing one first (reuse).
    Out-of-plant questions are refused before this is called (other_plant)."""
    if _COMMERCIAL.search(text):
        return Suggestions("Sales and plan numbers are for management and finance, so they are not in your floor view. "
                           "Ask your manager, or use Other department to request what you need.")
    options = menu(steward, user, supply)
    metrics, need = words_to_metrics(text)
    reply, by_ai, items = "", False, []
    if steward.llm is not None:
        try:
            raw = steward.llm.generate_json(render_prompt(
                steward.settings.prompts_dir, "worker_suggest", department=user.department or user.role,
                plant=user.plant, question=text, menu="\n".join(f"- {k}: {v}" for k, v in options.items()),
            ))
            picks = [p for p in raw.get("picks", []) if isinstance(p, dict) and p.get("id") in options]
            items = [Suggestion(p["id"], _label(p["id"], options[p["id"]]), str(p.get("why", ""))[:80]) for p in picks]
            items = _on_topic(steward, items, metrics)
            reply, by_ai = " ".join(str(raw.get("reply", "")).split()), bool(items)
        except Exception:
            logger.warning("worker_suggest_failed", exc_info=True)
    if not items:
        usual = [m for p in PROMPTS.get(user.department or "", []) for m in p.metric_ids]
        picked = metrics or usual  # a specific question gets its own numbers only; a broad one the department's usual
        items = [Suggestion(f"kpi:{m}", options[f"kpi:{m}"]) for m in picked if f"kpi:{m}" in options]
        reply = (f"{need[0].upper() + need[1:]} is not in governed data yet. " if need else "") + (
            "Here is what you can open now." if metrics else f"Here is what {user.department or 'your team'} usually "
            "checks first.")
    if _WANTS_REPORT.search(text) and not any(i.id.startswith("report:") for i in items):
        best = _best_report(steward, options, [i.id.partition(":")[2] for i in items] or metrics)
        if best:
            items.insert(0, Suggestion(best, _label(best, options[best]), "existing dashboard with these numbers"))
            if not by_ai:
                reply = f"The existing dashboard {options[best].split(' (')[0]} already shows some of these. " + reply
    return Suggestions(reply, _unique(items)[:MAX_PICKS], by_ai)


def _best_report(steward, options: dict[str, str], wanted: list[str]) -> str:
    """The menu report carrying most of the wanted numbers (menu order breaks ties: most floor KPIs, certified...)."""
    reports = [k for k in options if k.startswith("report:")]
    if not reports:
        return ""
    want = set(wanted) or OPS_METRICS

    def hits(key: str) -> int:
        return len(artifact_covered_metrics(steward.catalog.artifacts[key.partition(":")[2]], steward.catalog) & want)

    best = max(reports, key=hits)  # max keeps the first of equals = menu order
    return best if hits(best) else ""


def _label(item_id: str, text: str) -> str:
    """Chip text: a KPI by name; a report as "Dashboard: <title>" so the worker sees it is an existing dashboard."""
    title = text.split(" (")[0]
    return f"Dashboard: {title}" if item_id.startswith("report:") else title


def _unique(items: list[Suggestion]) -> list[Suggestion]:
    seen: set[str] = set()
    return [s for s in items if not (s.id in seen or seen.add(s.id))]


def open_item(steward, user: User, item_id: str, supply) -> WorkerAnswer:
    """A picked suggestion, reuse only: one KPI -> its best visible report; a report -> that report's KPIs."""
    kind, _, key = item_id.partition(":")
    if kind == "kpi":
        return reuse_only(steward, user, [key], steward.catalog.metrics[key].name, supply)
    asset = steward.catalog.artifacts[key]
    metrics = sorted(artifact_covered_metrics(asset, steward.catalog))
    return reuse_only(steward, user, metrics, asset.title, supply, prefer=key)
