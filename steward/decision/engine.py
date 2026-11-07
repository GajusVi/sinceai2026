from __future__ import annotations

from datetime import date

from ..catalog import Catalog
from ..config import EXTEND_MIN_COVERAGE, REUSE_MIN_COVERAGE, REUSE_MIN_TRUST
from ..linking import kpi_index
from ..models import Candidate, Decision, Evidence, Gap, GapKind, ParsedQuestion, Verdict
from ..search import SearchHit
from . import fit
from .conflicts import find_conflicts
from .consolidate import cluster_evidence, duplicate_clusters
from .feasible import not_feasible
from .lifecycle import add_lifecycle
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


def _is_tableau(candidate: Candidate) -> bool:
    return candidate.artifact.platform == "Tableau"


def _reuse_eligible(c: Candidate, catalog: Catalog | None = None, as_of: date | None = None) -> bool:
    """Covers everything, trusted enough, Power BI, and (C2) not retiring and not on a failed refresh."""
    ok = c.coverage >= REUSE_MIN_COVERAGE and c.trust >= REUSE_MIN_TRUST and not _is_tableau(c)
    return ok and (catalog is None or fit.healthy(c.artifact, catalog, as_of))


def _with_all_carriers(question: ParsedQuestion, hits: list[SearchHit], catalog: Catalog) -> list[SearchHit]:
    """F2: every asset that carries a requested KPI is a candidate, also when text search ranked it below the top 40.
    Search order still breaks ties (search_score, 10% of the candidate score)."""
    if not kpi_index(catalog)[0]:  # sample catalog: goldens unchanged
        return hits
    seen = {h.artifact.id for h in hits}
    extra = sorted(fit.carriers(question, catalog) - seen)
    return hits + [SearchHit(catalog.artifact(i), 0.0, {}) for i in extra]


def _with_duplicates(
    decision: Decision, candidates: list[Candidate], catalog: Catalog, as_of: date | None = None
) -> Decision:
    """CONSOLIDATE precedence, option A (Gajus): the best asset answers the question. When it sits in a duplicate cluster
    (same product scope, KPI Jaccard >= CONSOLIDATE_JACCARD) the verdict is CONSOLIDATE only if no member is REUSE-eligible;
    otherwise the verdict stays and the duplicates ride along as a CONSOLIDATE flag with RULE-001 evidence."""
    if not decision.best or not kpi_index(catalog)[0]:  # the sample catalog has no KPI ids: goldens unchanged
        return decision
    pool = [c for c in candidates if c.coverage >= EXTEND_MIN_COVERAGE]
    cluster = next(
        (
            c
            for c in duplicate_clusters(pool, catalog)
            if decision.best.artifact.id in {m.artifact.id for m in c.members}
        ),
        None,
    )
    if cluster is None:
        return decision
    evidence = [e for e in decision.evidence if e.rule_id != "RULE-006"] + cluster_evidence(cluster)
    if any(_reuse_eligible(m, catalog, as_of) for m in cluster.members):
        return decision.model_copy(
            update={
                "evidence": decision.evidence + cluster_evidence(cluster),
                "flags": [*decision.flags, "CONSOLIDATE"],
            }
        )
    keeper = cluster.keeper
    if not fit.healthy(keeper.artifact, catalog, as_of):  # C2: a retiring or failing report is never the keeper
        return decision
    flags = ["CONSOLIDATE"]
    if _is_tableau(keeper):
        flags.append("MIGRATE")
        evidence.append(_tableau_evidence(keeper))
    ids = {m.artifact.id for m in cluster.members}
    others = cluster.others + [c for c in candidates if c.artifact.id not in ids][:2]
    return decision.model_copy(
        update={
            "verdict": Verdict.CONSOLIDATE,
            "best": keeper,
            "alternatives": others,
            "evidence": evidence,
            "flags": flags,
            "reasons": [
                f"{len(cluster.members)} reports repeat the same metrics for the same product; none is good enough to reuse as is.",
                f"Keep {keeper.artifact.id} (trust {keeper.trust:.2f}), retire {', '.join(c.artifact.id for c in cluster.others)}.",
            ],
        }
    )


def _certify(best: Candidate) -> list[Evidence]:
    """C2: a missing endorsement does not block REUSE; it is an action attached to it."""
    a = best.artifact
    if not a.platform or a.endorsement in ("certified", "promoted"):
        return []
    return [
        Evidence(
            claim=f"Reuse {a.id} and have it certified: it is not endorsed yet (C2: an action, not a block)",
            record_ids=[a.id],
            severity="info",
        )
    ]


def _tableau_evidence(best: Candidate) -> Evidence:
    return Evidence(
        claim=f"{best.artifact.id} is on Tableau: rationalise before migrating, no 1:1 recreation (RULE-006)",
        rule_id="RULE-006",
        record_ids=[best.artifact.id],
        severity="warning",
    )


def conflict_evidence(conflicts: list, catalog: Catalog, limit: int = 10) -> list[Evidence]:
    """RULE-002: an asset uses a variant KPI instead of the approved one. Suggests the canonical id."""
    variants = kpi_index(catalog)[1]
    out = []
    for c in conflicts[:limit]:
        status = variants.get(c.artifact_formula, ("", "variant"))[1]
        if not c.artifact_formula.startswith("KPI-"):
            continue
        out.append(
            Evidence(
                claim=f"{c.artifact_id} uses {c.artifact_formula} ({status}); use the approved {c.official_formula} instead",
                rule_id="RULE-002",
                record_ids=[c.artifact_id, c.artifact_formula, c.official_formula],
                severity="warning",
            )
        )
    return out


def decide(question: ParsedQuestion, hits: list[SearchHit], catalog: Catalog, as_of: date) -> Decision:
    decision = _decide(question, _with_all_carriers(question, hits, catalog), catalog, as_of)
    decision.evidence.extend(conflict_evidence(decision.conflicts, catalog))
    return add_lifecycle(decision, catalog, as_of)


def _decide(question: ParsedQuestion, hits: list[SearchHit], catalog: Catalog, as_of: date) -> Decision:
    conflicts = find_conflicts(question.metrics, catalog)

    infeasible = not_feasible(question, catalog)
    if infeasible:
        infeasible.conflicts = conflicts
        return infeasible

    if question.unmapped_terms or question.conflicts:
        evidence = [
            Evidence(claim=f"Not in the governed dictionary: '{term}'", rule_id=None, severity="blocker")
            for term in question.unmapped_terms
        ] + [
            Evidence(claim=f"Conflict in the request: {c}", rule_id=None, severity="blocker")
            for c in question.conflicts
        ]
        reasons = []
        if question.unmapped_terms:
            reasons.append(
                "These terms are not in the governed dictionary: " + ", ".join(question.unmapped_terms) + "."
            )
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
    best = _choose(eligible, question, catalog, as_of)
    alternatives = [c for c in candidates if c is not best][:4]

    if best and _reuse_eligible(best, catalog, as_of):
        return _with_duplicates(
            Decision(
                verdict=Verdict.REUSE,
                best=best,
                alternatives=alternatives,
                conflicts=conflicts,
                reasons=[
                    "The report covers every part of the question.",
                    f"Trust {best.trust:.2f} meets the threshold {REUSE_MIN_TRUST}.",
                ],
                evidence=_certify(best),
            ),
            candidates,
            catalog,
            as_of,
        )

    covers_a_metric = best is not None and any(i.startswith(f"{GapKind.METRIC.value}:") for i in best.covered)
    if best and covers_a_metric and _extend_enough(best, question, catalog):
        reasons = [f"The report covers {best.coverage:.0%} of the question and contains the required metric."]
        flags: list[str] = []
        evidence: list[Evidence] = []
        if _is_tableau(best):
            flags.append("MIGRATE")
            best.gaps.append(Gap(kind=GapKind.TRUST, key="platform"))
            reasons.append(
                "It is a Tableau report: Tableau is never reused as is, the extension is a Power BI version (migrate, do not copy 1:1)."
            )
            evidence.append(
                Evidence(
                    claim=f"{best.artifact.id} is on Tableau: rationalise before migrating, no 1:1 recreation (RULE-006)",
                    rule_id="RULE-006",
                    record_ids=[best.artifact.id],
                    severity="warning",
                )
            )
        elif best.coverage >= REUSE_MIN_COVERAGE:
            best.gaps.extend(trust_gaps(best.artifact, as_of))
            reasons.append(
                f"Trust {best.trust:.2f} is below the threshold {REUSE_MIN_TRUST}: it needs an owner or certification."
            )
        extend = Decision(
            verdict=Verdict.EXTEND,
            best=best,
            alternatives=alternatives,
            conflicts=conflicts,
            reasons=reasons,
            evidence=evidence,
            flags=flags,
        )
        return _with_duplicates(extend, candidates, catalog, as_of)

    blocked = [
        c
        for c in eligible
        if fit.metric_share(c, question) > 0 and fit.health_problems(c.artifact, catalog, as_of)
    ]
    blocked.sort(key=lambda c: -fit.metric_share(c, question))  # the one carrying most of the request first
    if not covers_a_metric and blocked:
        top = blocked[0]
        return Decision(
            verdict=Verdict.CREATE,
            alternatives=blocked[:4],
            conflicts=conflicts,
            reasons=[
                f"Only reports that must not be the answer carry these metrics: {top.artifact.id} "
                f"({', '.join(fit.health_problems(top.artifact, catalog, as_of))})."
            ],
            evidence=[
                Evidence(
                    claim=f"{c.artifact.id} is not used as a base: "
                    f"{', '.join(fit.health_problems(c.artifact, catalog, as_of))} (C2)",
                    record_ids=[c.artifact.id],
                    severity="warning",
                )
                for c in blocked[:3]
            ],
        )
    if not covers_a_metric:
        return Decision(
            verdict=Verdict.CREATE,
            alternatives=candidates[:4],
            conflicts=conflicts,
            reasons=["No compatible report contains the required metric with the official formula."],
        )
    share = fit.metric_share(best, question)
    return Decision(
        verdict=Verdict.CREATE,
        best=best,
        alternatives=alternatives,
        conflicts=conflicts,
        reasons=[
            f"The closest report carries only {share:.0%} of the requested metrics "
            f"(an extension needs at least {fit.EXTEND_MIN_METRIC_SHARE:.0%})."
        ],
    )


def _extend_enough(best: Candidate, question: ParsedQuestion, catalog: Catalog) -> bool:
    """C1 on the data pack: at least half of the requested KPIs (filters do not count). Sample catalog: item share."""
    if kpi_index(catalog)[0]:
        return fit.metric_share(best, question) >= fit.EXTEND_MIN_METRIC_SHARE
    return best.coverage >= EXTEND_MIN_COVERAGE


def _choose(eligible: list[Candidate], question: ParsedQuestion, catalog: Catalog, as_of: date) -> Candidate | None:
    """The candidate the verdict is about. Lifecycle comes before the choice (C2): a retiring or failing report is never
    chosen. Among the rest, a REUSE-eligible report wins over a higher-scored one that is not (Martynas B1)."""
    if not kpi_index(catalog)[0]:
        return eligible[0] if eligible else None
    pool = [c for c in eligible if fit.healthy(c.artifact, catalog, as_of)]
    reusable = [c for c in pool if _reuse_eligible(c, catalog, as_of)]
    if reusable:
        return reusable[0]
    # most of the requested KPIs first, then the candidate score (stable: search order breaks ties)
    return max(pool, key=lambda c: (fit.metric_share(c, question), c.score), default=None)
