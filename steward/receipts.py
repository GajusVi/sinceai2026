"""The receipt strip (DECISION T2.5, C6): every step of the chain says what went in, what came out, why, and what it
cost. It is the pipeline Panu asked to see (08_PANU_QA point 8), produced by the product for every request.

- `gates(candidate, ...)`: the checklist behind the verdict, per candidate report, in a fixed order. The first failing
  gate is the reason the report is not simply reused, and names the action that would fix it (gajus-attack 5.1,
  Margiris's checklist, Gajus B1). It reads the same checks as the engine (decision/fit.py), never its own copy.
- `receipts(result, intent, ...)`: one line per step, from the result the chain already produced (no new decisions).
- `Meter`: wraps the LLM client's calls, so each phase reports its milliseconds and its AI calls.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date

from .models import Candidate, GapKind, StewardResult, Verdict


@dataclass
class Gate:
    name: str
    ok: bool
    detail: str = ""
    action: str = ""  # what fixes it when it fails (certify, REASSIGN_OWNER, FIX_REFRESH, ...)


@dataclass
class Receipt:
    step: str
    inp: str
    out: str
    why: str = ""
    ms: float | None = None
    llm_calls: int = 0
    failed: str = ""  # an AI call that failed and what answered instead (rules, template, cache)
    gates: list[Gate] = field(default_factory=list)
    ids: list[str] = field(default_factory=list)


def gates(
    candidate: Candidate, metrics: list[str], catalog, as_of: date | None, feasible: dict[str, bool]
) -> list[Gate]:
    """The checklist for one candidate report. Order = the order a reviewer would ask in."""
    from .decision import fit
    from .decision.engine import REUSE_MIN_TRUST

    a = candidate.artifact
    names = {m: catalog.metrics[m].name for m in metrics if m in catalog.metrics}
    covered = {c.split(":", 1)[1] for c in candidate.covered if c.startswith(f"{GapKind.METRIC.value}:")}
    missing = [names.get(m, m) for m in metrics if m not in covered]
    problems = fit.health_problems(a, catalog, as_of)
    no_data = [n for n, ok in feasible.items() if not ok]
    owner_ok = bool(a.owner) and getattr(a, "owner_status", "active") in ("active", "", None)
    endorsed = getattr(a, "endorsement", "") in ("certified", "promoted")
    out = [
        Gate(
            "Has every requested KPI",
            not missing,
            f"{len(metrics) - len(missing)} of {len(metrics)}" + (f"; missing {', '.join(missing)}" if missing else ""),
            "extend it with the missing KPIs" if missing else "",
        ),
        Gate(
            "Scope fits the request",
            candidate.compatible,
            "" if candidate.compatible else "locked to another scope",
            "" if candidate.compatible else "not usable as a base",
        ),
        Gate(
            "On Power BI",
            a.platform != "Tableau",
            a.platform or "",
            "MIGRATE (rationalise, no 1:1 copy)" if a.platform == "Tableau" else "",
        ),
        Gate(
            "Refresh healthy",
            "failed refresh" not in problems,
            getattr(a, "refresh_status", "") or "",
            "FIX_REFRESH" if "failed refresh" in problems else "",
        ),
        Gate(
            "Not being retired",
            "recommended for retirement" not in problems,
            "",
            "do not build on it" if "recommended for retirement" in problems else "",
        ),
        Gate("Owner active", owner_ok, a.owner or "no owner", "" if owner_ok else "REASSIGN_OWNER"),
        Gate("Certified or promoted", endorsed, getattr(a, "endorsement", "") or "none", "" if endorsed else "certify"),
        Gate("Trusted enough", candidate.trust >= REUSE_MIN_TRUST, f"trust {candidate.trust:.2f}", ""),
    ]
    if feasible:
        out.append(
            Gate(
                "Governed data for every KPI",
                not no_data,
                "" if not no_data else "no source data: " + ", ".join(no_data),
                "" if not no_data else "ask the KPI owner for the source",
            )
        )
    return out


def first_failure(checks: list[Gate]) -> Gate | None:
    return next((g for g in checks if not g.ok), None)


class Meter:
    """Counts AI calls and time per phase. Wraps the client's methods in place (all parts of the chain share it)."""

    def __init__(self, llm) -> None:
        self.calls = 0
        self.failures = 0
        self.phases: dict[str, dict] = {}
        if llm is None:
            return
        for name in ("generate_json", "generate_text"):
            fn = getattr(llm, name, None)
            if fn is not None and not getattr(fn, "_metered", False):
                setattr(llm, name, self._wrap(fn))

    def _wrap(self, fn):
        def call(*args, **kwargs):
            self.calls += 1
            try:
                return fn(*args, **kwargs)
            except Exception:
                self.failures += 1
                raise

        call._metered = True
        return call

    @contextmanager
    def phase(self, name: str, into: dict | None = None):
        """Time and AI calls of one phase, added to `into` (a session's own dict) or to this meter's."""
        target = self.phases if into is None else into
        t0, c0, f0 = time.perf_counter(), self.calls, self.failures
        try:
            yield
        finally:
            p = target.setdefault(name, {"ms": 0.0, "llm": 0, "failed": 0})
            p["ms"] += (time.perf_counter() - t0) * 1000
            p["llm"] += self.calls - c0
            p["failed"] += self.failures - f0

    def take(self) -> dict[str, dict]:
        """The phases measured since the last take (one request)."""
        out, self.phases = self.phases, {}
        return out


def receipts(
    result: StewardResult,
    intent,
    catalog,
    as_of: date | None,
    phases: dict[str, dict] | None = None,
    total_assets: int | None = None,
) -> list[Receipt]:
    """One line per step of the chain, from what the chain already produced."""
    from .decision import fit

    phases = phases or {}
    d, spec, q = result.decision, result.spec, result.question
    metrics = list(q.metrics)
    names = [catalog.metrics[m].name for m in metrics if m in catalog.metrics]

    def cost(name: str) -> dict:
        p = phases.get(name, {})
        failed = f"{p['failed']} AI call(s) failed; rules answered" if p.get("failed") else ""
        return {"ms": p.get("ms"), "llm_calls": p.get("llm", 0), "failed": failed}

    scope = []
    if intent is not None:
        scope = [*[p for p in intent.products if p != "All Pharma"], *intent.markets, *intent.regions, *intent.sites]
        source = (
            f"interview, {getattr(intent, 'mode', '')}".rstrip(", ") if getattr(intent, "mode", "") else "interview"
        )
    else:
        scope = [v for v in q.filters.values()]
        source = q.parser or "parser"
    out = [
        Receipt(
            "Understand",
            f'"{q.text}"',
            (", ".join(names) or "no governed KPI") + (f" · {', '.join(scope)}" if scope else " · all scope"),
            f"read by the {source}; ids checked against the catalog",
            **cost("understand"),
        )
    ]

    n_assets = total_assets or len(catalog.artifacts)
    carriers = fit.carriers(q, catalog) if metrics else set()
    out.append(
        Receipt(
            "Find what exists",
            f"{len(metrics)} KPI(s)",
            f"{len(carriers)} of {n_assets} reports carry at least one of them",
            "every report checked through the KPI index, not a text search",
            ids=sorted(carriers)[:6],
        )
    )

    feasible = {m.name: m.feasible for m in (spec.measures if spec else [])}
    checks = gates(d.best, metrics, catalog, as_of, feasible) if d.best else []
    fail = first_failure(checks)
    best = f"{d.best.artifact.id} {d.best.artifact.title}" if d.best else "no report fits"
    if d.verdict == Verdict.REUSE:
        why = "every check passes" if not fail else f"reusable; attached action: {fail.action or fail.name}"
    elif fail:
        why = f"first failing check: {fail.name}" + (f" ({fail.detail})" if fail.detail else "")
    else:
        why = (d.reasons or [""])[0]
    out.append(Receipt("Decide", best, d.verdict.value, why, gates=checks, ids=[d.best.artifact.id] if d.best else [], **cost("decide")))
    if spec is not None:
        gaps = [m.name for m in spec.measures if not m.feasible]
        out.append(
            Receipt(
                "Check the data",
                f"{len(spec.measures)} measure(s)",
                f"{len(spec.measures) - len(gaps)} with governed data"
                + (f", {len(gaps)} labelled gap(s)" if gaps else ""),
                "a KPI without source data is shown as a gap, never as a number",
            )
        )
        visuals = [v for p in spec.pages for v in p.visuals]
        src = spec.provenance.get("layout_source", "template")
        hidden = spec.provenance.get("layout_hidden", "")
        out.append(
            Receipt(
                "Build the dashboard",
                f"{d.verdict.value} for {spec.provenance.get('layout_role', '?')}",
                f"{len(visuals)} visuals, layout by {'AI' if src == 'llm' else 'rules'}",
                f"not shown for this role: {hidden}" if hidden else "ordered for the reader's role",
                **cost("build"),
            )
        )
        lint = spec.lint or []
        blocks = [r.rule_id for r in lint if r.status == "block"]
        warns = [r.rule_id for r in lint if r.status == "warn"]
        out.append(
            Receipt(
                "Governance checks",
                f"{len(lint)} rules",
                f"{len(lint) - len(blocks) - len(warns)} pass, {len(warns)} warn, {len(blocks)} block",
                ("approve is blocked by " + ", ".join(blocks)) if blocks else "the approve button is enabled",
            )
        )
    out.append(
        Receipt(
            "Approve",
            "one accountable person (BI team)",
            "nothing is published until a builder approves"
            if d.verdict != Verdict.REUSE
            else "existing report: nothing to approve",
            "every decision is written to the journal",
        )
    )
    if phases.get("explain", {}).get("llm") or result.investigation is not None:  # only when an AI explanation ran
        out.insert(
            3,
            Receipt(
                "Explain",
                "the decision and its evidence",
                "investigation + plain-language why",
                "advisory: the AI never changes the verdict",
                **cost("explain"),
            ),
        )
    return out
