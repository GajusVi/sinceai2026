"""AI investigation (AI-first, Sat 7 Nov): the LLM reads the evidence dossier our tools collected and explains, step by
step with record ids, what it found and what it recommends. The verdict stays the rules engine's; a disagreement is
shown, never applied. Validation: cited ids must be in the dossier, every number must appear in the dossier, the
recommendation must be a known verdict. No LLM or a failed check -> None (the screen shows the rules evidence only).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .llm import LLMClient
from .models import Decision, Investigation, InvestigationStep, Verdict
from .prompts import render_prompt

logger = logging.getLogger(__name__)
MAX_CANDIDATES = 5
_ID = re.compile(r"\b(?:AST|OWN|KPI|RULE|SM|DQ|REQ|WS)-\d+\b")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def _asset_line(a, extra: str = "") -> str:
    users = [u.unique_users for u in a.usage]
    avg = f"{sum(users) / len(users):.0f}" if users else "no usage data"
    return (
        f'{a.id} "{a.title}" | platform {a.platform or "?"} | product {a.product_scope or "?"}, '
        f"market {a.market_scope or '?'} | KPIs {', '.join(a.kpi_ids) or 'none'}{extra} | "
        f"owner {a.owner_id or 'none'} ({a.owner_status or 'missing'}) | model {a.model_id or '?'} refresh "
        f"{a.refresh_status or '?'}, endorsement {a.endorsement} | avg monthly users {avg}"
    )


def dossier(decision: Decision, estate: list | None = None, gaps: list[str] | None = None) -> str:
    """What the tools found, as plain lines. Everything the model may cite or quote comes from here.
    `estate` = other assets of the requested products (the search may miss them when the request names no KPI)."""
    lines: list[str] = ["Search results (ranked):"]
    cands = ([decision.best] if decision.best else []) + decision.alternatives[: MAX_CANDIDATES - 1]
    for rank, c in enumerate(cands, 1):
        extra = (
            f" | covers {c.coverage:.0%} of the request | trust {c.trust:.2f} | "
            f"still missing: {', '.join(g.key for g in c.gaps) or 'nothing'}"
        )
        lines.append(f"{rank}. " + _asset_line(c.artifact, extra))
    if not cands:
        lines.append("No existing asset is compatible with the request.")
    seen = {c.artifact.id for c in cands}
    others = [a for a in estate or [] if a.id not in seen][:6]
    if others:
        lines.append("Other assets of the requested product(s) in the estate:")
        lines += ["- " + _asset_line(a) for a in others]
    lines.append("Governance findings:")
    for e in decision.evidence[:12]:
        ids = f" [{', '.join(e.record_ids)}]" if e.record_ids else ""
        rule = f"{e.rule_id}: " if e.rule_id else ""
        lines.append(f"- {e.severity}: {rule}{e.claim}{ids}" + (f" ({e.value})" if e.value else ""))
    for conflict in decision.conflicts[:4]:
        lines.append(
            f'- KPI conflict: {conflict.artifact_id} uses "{conflict.label}" ({conflict.metric_id}), '
            "not the canonical definition"
        )
    if decision.flags:
        lines.append("Flags: " + ", ".join(decision.flags))
    for gap in gaps or []:
        lines.append(f"- governed KPI without source data: {gap}")
    return "\n".join(lines)


def investigate(
    llm: LLMClient | None,
    prompts_dir: Path,
    question: str,
    intent_text: str,
    decision: Decision,
    estate: list | None = None,
    gaps: list[str] | None = None,
) -> Investigation | None:
    if llm is None:
        return None
    facts = dossier(decision, estate, gaps)
    try:
        raw = llm.generate_json(
            render_prompt(
                prompts_dir,
                "investigate",
                question=question,
                intent=intent_text,
                dossier=facts,
                verdict=decision.verdict.value,
                best=decision.best.artifact.id if decision.best else "no asset",
            )
        )
        return validate(raw, facts, decision)
    except Exception:
        logger.warning("llm_investigate_failed", exc_info=True)
        return None


def validate(raw: dict, facts: str, decision: Decision) -> Investigation:
    """Drops steps that cite unknown ids or quote numbers the dossier does not contain; raises if nothing is left."""
    known_ids = set(_ID.findall(facts))
    known_numbers = set(_NUMBER.findall(facts))
    steps: list[InvestigationStep] = []
    dropped = 0
    for s in raw.get("steps") or []:
        finding = str(s.get("finding", "")).strip()
        ids = [str(i) for i in s.get("record_ids") or []]
        cited = set(ids) | set(_ID.findall(finding))
        numbers = {n for n in _NUMBER.findall(_ID.sub("", finding))}
        if not finding or not cited <= known_ids or not numbers <= known_numbers:
            dropped += 1
            continue
        steps.append(InvestigationStep(finding=finding, record_ids=[i for i in ids if i in known_ids]))
    if not steps:
        raise ValueError("no grounded step")
    rec = str(raw.get("recommendation", "")).strip().upper()
    if rec not in {v.value for v in Verdict}:
        rec = ""
    why = str(raw.get("why", "")).strip()
    if set(_NUMBER.findall(_ID.sub("", why))) - known_numbers:
        why = ""
    risks = [str(r).strip() for r in raw.get("risks") or [] if str(r).strip()][:3]
    risks = [r for r in risks if not (set(_NUMBER.findall(_ID.sub("", r))) - known_numbers)]
    asset = str(raw.get("best_asset_id") or "").strip()
    asset = asset if asset in known_ids and asset.startswith("AST-") else ""
    rules_asset = decision.best.artifact.id if decision.best else ""
    same_verdict = not rec or rec == decision.verdict.value
    same_asset = not asset or not rules_asset or asset == rules_asset
    return Investigation(
        steps=steps,
        recommendation=rec,
        best_asset_id=asset,
        agrees=same_verdict and same_asset,
        why=why,
        risks=risks,
        dropped_steps=dropped,
    )
