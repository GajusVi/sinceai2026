from __future__ import annotations

from datetime import date

from ..catalog import Catalog
from ..config import EXTEND_MIN_COVERAGE, REUSE_MIN_COVERAGE, REUSE_MIN_TRUST
from ..models import Candidate, Decision, Evidence, GapKind, ParsedQuestion, Verdict
from ..search import SearchHit
from .conflicts import find_conflicts
from .signals import coverage, trust, trust_gaps


def score_candidates(question: ParsedQuestion, hits: list[SearchHit], catalog: Catalog, as_of: date) -> list[Candidate]:
    if not hits:
        return []
    top_search = max(h.score for h in hits)
    candidates = []
    for hit in hits:
        share, covered, gaps, compatible = coverage(question, hit.artifact, catalog)
        trust_score = trust(hit.artifact, as_of)
        search_norm = hit.score / top_search if top_search else 0.0
        candidates.append(
            Candidate(
                artifact=hit.artifact,
                search_score=round(hit.score, 4),
                coverage=share,
                trust=trust_score,
                covered=covered,
                gaps=gaps,
                compatible=compatible,
                score=round(0.6 * share + 0.3 * trust_score + 0.1 * search_norm, 4),
            )
        )
    return sorted(candidates, key=lambda c: (c.compatible, c.score), reverse=True)


def decide(question: ParsedQuestion, hits: list[SearchHit], catalog: Catalog, as_of: date) -> Decision:
    conflicts = find_conflicts(question.metrics, catalog)

    if question.unmapped_terms or question.conflicts:
        evidence = [
            Evidence(claim=f"Not in the governed dictionary: '{term}'", rule_id=None, severity="blocker")
            for term in question.unmapped_terms
        ] + [Evidence(claim=f"Conflict in the request: {c}", rule_id=None, severity="blocker") for c in question.conflicts]
        reasons = []
        if question.unmapped_terms:
            reasons.append("These terms are not in the governed dictionary: " + ", ".join(question.unmapped_terms) + ".")
        if question.conflicts:
            reasons.append("The request contradicts itself: " + "; ".join(question.conflicts) + ".")
        return Decision(verdict=Verdict.CLARIFY, conflicts=conflicts, reasons=reasons, evidence=evidence)

    if not question.metrics:
        return Decision(
            verdict=Verdict.CLARIFY,
            conflicts=conflicts,
            reasons=["No metric from the dictionary was found in the question."],
        )

    candidates = score_candidates(question, hits, catalog, as_of)
    eligible = [c for c in candidates if c.compatible]
    best = eligible[0] if eligible else None
    alternatives = [c for c in candidates if c is not best][:4]

    if best and best.coverage >= REUSE_MIN_COVERAGE and best.trust >= REUSE_MIN_TRUST:
        return Decision(
            verdict=Verdict.REUSE,
            best=best,
            alternatives=alternatives,
            conflicts=conflicts,
            reasons=[
                "The report covers every part of the question.",
                f"Trust {best.trust:.2f} meets the threshold {REUSE_MIN_TRUST}.",
            ],
        )

    covers_a_metric = best is not None and any(i.startswith(f"{GapKind.METRIC.value}:") for i in best.covered)
    if best and covers_a_metric and best.coverage >= EXTEND_MIN_COVERAGE:
        reasons = [f"The report covers {best.coverage:.0%} of the question and contains the required metric."]
        if best.coverage >= REUSE_MIN_COVERAGE:
            best.gaps.extend(trust_gaps(best.artifact, as_of))
            reasons.append(f"Trust {best.trust:.2f} is below the threshold {REUSE_MIN_TRUST}: it needs an owner or certification.")
        return Decision(verdict=Verdict.EXTEND, best=best, alternatives=alternatives, conflicts=conflicts, reasons=reasons)

    if not covers_a_metric:
        return Decision(
            verdict=Verdict.CREATE,
            alternatives=candidates[:4],
            conflicts=conflicts,
            reasons=["No compatible report contains the required metric with the official formula."],
        )
    return Decision(
        verdict=Verdict.CREATE,
        best=best,
        alternatives=alternatives,
        conflicts=conflicts,
        reasons=[f"The closest report covers only {best.coverage:.0%} of the question."],
    )
