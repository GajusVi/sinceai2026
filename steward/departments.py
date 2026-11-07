"""Which governed KPIs each plant department sees first (Gajus, Sat 17:40: AI proposes, builder approves).

The AI drafts a department -> KPI map from the governed KPI list; code keeps only real metric ids (max 4 each); a
builder edits and approves it in the app. Workers only ever read the APPROVED map (steward/worker.py), so what the
floor sees is consistent day to day and every change has a name and a time. Relevance only: access stays rule-based
(steward/auth.py), never decided by the model. No approved map yet = the built-in defaults (worker.PROMPTS).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from .prompts import render_prompt

logger = logging.getLogger(__name__)
FILE = "department_kpis.json"  # in the steward data dir: approved map, open draft, change log
MAX_PER_DEPARTMENT = 4


def defaults() -> dict[str, list[str]]:
    from .worker import PROMPTS  # local import: worker imports this module

    out: dict[str, list[str]] = {}
    for dept, prompts in PROMPTS.items():
        out[dept] = list(dict.fromkeys(m for p in prompts for m in p.metric_ids))[:MAX_PER_DEPARTMENT]
    return out


def propose(llm, prompts_dir: Path, catalog, departments: list[str]) -> dict:
    """Draft: {"map": {dept: [metric ids]}, "why": {metric@dept: text}, "missing": {dept: [...]}, "source": ai|default}.
    The model's ids are checked against the catalog; unknown ids and unknown departments are dropped."""
    metrics = catalog.metrics
    draft = {"map": defaults(), "why": {}, "missing": {}, "source": "default"}
    if llm is None:
        return draft
    by_kpi = {m.kpi_id: m.id for m in metrics.values() if m.kpi_id}
    lines = "\n".join(f"- {m.kpi_id or m.id}: {m.name} ({m.domain}, {m.unit or '-'})" for m in metrics.values())
    try:
        raw = llm.generate_json(render_prompt(prompts_dir, "departments", departments=", ".join(departments),
                                              kpis=lines))
    except Exception:
        logger.warning("department_map_failed", exc_info=True)
        return draft
    mapping, why = {}, {}
    for dept in departments:
        picks = (raw.get("map") or {}).get(dept) or []
        ids = []
        for p in picks if isinstance(picks, list) else []:
            key = p.get("id") if isinstance(p, dict) else p
            metric = by_kpi.get(key) or (key if key in metrics else None)
            if metric and metric not in ids:
                ids.append(metric)
                why[f"{metric}@{dept}"] = str(p.get("why", ""))[:100] if isinstance(p, dict) else ""
        mapping[dept] = ids[:MAX_PER_DEPARTMENT]
    if not any(mapping.values()):
        return draft
    missing = {d: [str(x)[:60] for x in v][:5] for d, v in (raw.get("missing") or {}).items() if d in departments}
    return {"map": mapping, "why": why, "missing": missing, "source": "ai"}


def _read(data_dir: Path) -> dict:
    path = data_dir / FILE
    if not path.exists():
        return {"approved": None, "draft": None, "log": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(data_dir: Path, state: dict) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / FILE).write_text(json.dumps(state, indent=2), encoding="utf-8")


def save_draft(data_dir: Path, draft: dict, actor: str) -> None:
    state = _read(data_dir)
    state["draft"] = {**draft, "by": actor, "at": _now()}
    state["log"].append({"at": _now(), "who": actor, "action": f"draft ({draft.get('source', '?')})"})
    _write(data_dir, state)


def approve(data_dir: Path, mapping: dict[str, list[str]], actor: str, catalog) -> dict[str, list[str]]:
    """The builder's edited map becomes the one workers read. Ids are checked again (the builder edits ids too)."""
    clean = {d: [m for m in ids if m in catalog.metrics][:MAX_PER_DEPARTMENT] for d, ids in mapping.items()}
    state = _read(data_dir)
    state["approved"] = {"map": clean, "by": actor, "at": _now()}
    state["draft"] = None
    state["log"].append({"at": _now(), "who": actor, "action": "approved",
                         "map": {d: ",".join(v) for d, v in clean.items()}})
    _write(data_dir, state)
    return clean


def approved(data_dir: Path) -> dict[str, list[str]] | None:
    found = _read(data_dir).get("approved")
    return found["map"] if found else None


def state(data_dir: Path) -> dict:
    return _read(data_dir)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
