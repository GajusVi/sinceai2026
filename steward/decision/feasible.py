"""NOT_FEASIBLE (BUILD_PLAN 2.1 / W3 gate G3): the question asks for numbers the governed data cannot give.

Two cases, both plain code:
  1. the metric is not in the KPI catalog at all ("batch yield"): no metric mapped, a metric-like word unmapped.
  2. every requested KPI is governed but has no source data (KPI-034 Gross-to-Net): `semantic.feasibility` finds none buildable.
A request that is only partly feasible keeps its normal verdict; the spec shows the gaps (rule DATA).
"""

from __future__ import annotations

from difflib import SequenceMatcher

from ..catalog import Catalog
from ..config import AMBIGUOUS_PHRASES, METRIC_NOUNS
from ..linking import kpi_index
from ..models import Decision, Evidence, ParsedQuestion, Verdict


def _nearest(phrase: str, catalog: Catalog, limit: int = 3) -> list[str]:
    """The governed, buildable metrics whose name or synonyms look most like the words asked for."""
    from ..intent import Intent
    from ..semantic import feasibility  # lazy: reads the data pack

    ranked = []
    for metric in catalog.metrics.values():
        if not metric.kpi_id:
            continue
        names = [metric.name, *metric.synonyms]
        ranked.append((max(SequenceMatcher(None, phrase.lower(), n.lower()).ratio() for n in names), metric))
    ranked.sort(key=lambda r: (-r[0], r[1].kpi_id))
    buildable = {m.kpi_id for m in feasibility(Intent(metric_ids=[m.kpi_id for _, m in ranked])).buildable}
    return [f"{m.kpi_id} {m.name}" for _, m in ranked if m.kpi_id in buildable][:limit]


def not_feasible(question: ParsedQuestion, catalog: Catalog) -> Decision | None:
    if not kpi_index(catalog)[0] or question.conflicts:  # sample catalog has no KPI ids
        return None
    words = [t for t in question.unmapped_terms if t.lower() in METRIC_NOUNS]
    ambiguous = [t for t in question.unmapped_terms if t.lower() in AMBIGUOUS_PHRASES]
    if not question.metrics and words and not ambiguous:
        phrase = " ".join(question.unmapped_terms)
        nearest = _nearest(phrase, catalog)
        evidence = [
            Evidence(
                claim=f"'{phrase}' is not a governed KPI: not in the KPI catalog, no approved definition or data",
                rule_id="DATA",
                severity="blocker",
            )
        ]
        evidence += [
            Evidence(claim=f"Nearest governed metric: {n}", record_ids=[n.split()[0]], severity="info") for n in nearest
        ]
        reasons = [f"'{phrase}' is not in the KPI catalog."]
        if nearest:
            reasons.append("Nearest governed metrics: " + "; ".join(nearest) + ".")
        return Decision(verdict=Verdict.NOT_FEASIBLE, reasons=reasons, evidence=evidence)
    if question.unmapped_terms or not question.metrics:
        return None
    from ..intent import intent_from_parsed
    from ..semantic import feasibility

    feas = feasibility(intent_from_parsed(question, catalog))
    if feas.buildable or not feas.gaps:
        return None
    evidence = [
        Evidence(
            claim=f"{m.kpi_id} {m.name}: {m.gap_reason or 'governed, but no source data'}",
            rule_id="DATA",
            record_ids=[m.kpi_id],
            severity="blocker",
        )
        for m in feas.gaps
    ]
    evidence += [
        Evidence(claim=f"Nearest buildable alternative: {n}", record_ids=[n.split()[0]], severity="info")
        for n in feas.nearest
    ]
    reasons = [
        "Governed, but no governed model holds the data: " + ", ".join(f"{m.kpi_id} {m.name}" for m in feas.gaps) + "."
    ]
    if feas.nearest:
        reasons.append("Nearest buildable alternatives: " + "; ".join(feas.nearest) + ".")
    return Decision(verdict=Verdict.NOT_FEASIBLE, reasons=reasons, evidence=evidence)
