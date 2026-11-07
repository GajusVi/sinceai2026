from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Protocol

from .catalog import Catalog
from .llm import LLMClient
from .models import Candidate, Decision, Gap, GapKind, ParsedQuestion, Verdict
from .prompts import render_prompt

logger = logging.getLogger(__name__)

TRUST_LABELS = {
    "certification": "certification by the domain owner",
    "owner": "an active owner",
    "freshness": "fresh data (last refresh is older than 30 days)",
}


class Explainer(Protocol):
    def explain(self, question: ParsedQuestion, decision: Decision, as_of: date) -> str: ...


class TemplateExplainer:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    def explain(self, question: ParsedQuestion, decision: Decision, as_of: date) -> str:
        parts = [self._verdict_text(question, decision, as_of)]
        parts += [self._conflict_text(c) for c in decision.conflicts]
        return "\n\n".join(parts)

    def gap_label(self, gap: Gap) -> str:
        if gap.kind == GapKind.METRIC:
            return f'metric "{self.catalog.metric(gap.key).name}"'
        if gap.kind == GapKind.FILTER:
            return f'filter "{self.catalog.dimension_value_label(gap.key, gap.value)}"'
        if gap.kind == GapKind.DIMENSION:
            return f'breakdown by "{self.catalog.dimension(gap.key).name}"'
        if gap.kind == GapKind.SCOPE:
            return f"report is limited to {self.catalog.dimension_value_label(gap.key, gap.value)}"
        return TRUST_LABELS.get(gap.key, gap.key)

    def _verdict_text(self, question: ParsedQuestion, decision: Decision, as_of: date) -> str:
        best = decision.best
        if decision.verdict == Verdict.CLARIFY:
            return (
                "**Please clarify the question.** Could not tell which metric you are looking for, e.g. revenue, margin or OTIF. "
                "If the metric is not in the dictionary yet, the domain owner has to define it first."
            )
        if decision.verdict == Verdict.NOT_FEASIBLE:
            return (
                "**Not possible with governed data.** "
                + " ".join(decision.reasons)
                + " Accept a buildable alternative, or file a data request for the missing source."
            )
        if decision.verdict == Verdict.REUSE:
            return (
                f'**Use "{best.artifact.title}"** ({best.artifact.owner}). '
                f"{self._trust_text(best, as_of)} It fully answers the question; no new report is needed."
            )
        if decision.verdict == Verdict.EXTEND:
            gaps = ", ".join(self.gap_label(g) for g in best.gaps)
            return (
                f'**Extend "{best.artifact.title}"** ({best.artifact.owner or "no owner assigned"}). '
                f"{self._trust_text(best, as_of)} It covers {best.coverage:.0%} of the question. "
                f"Missing: {gaps}. This is an extension of an existing report, not a new dashboard."
            )
        metrics = ", ".join(f'"{self.catalog.metric(m).name}"' for m in question.metrics)
        nearest = ""
        if best:
            missing = ", ".join(self.gap_label(g) for g in best.gaps if g.kind != GapKind.TRUST)
            nearest = f' The closest is "{best.artifact.title}", but it lacks: {missing}.'
        return (
            f"**No suitable report exists.**{nearest} Proposed: a new report built on the official metrics {metrics}. "
            "An owner must be assigned before it is created."
        )

    def _trust_text(self, candidate: Candidate, as_of: date) -> str:
        artifact = candidate.artifact
        age = (as_of - artifact.last_refreshed).days
        refreshed = "today" if age == 0 else "yesterday" if age == 1 else f"{age} days ago"
        certified = "Certified" if artifact.certified else "Not certified"
        return f"{certified}, refreshed {refreshed}, {artifact.views_30d} views in the last 30 days."

    def _conflict_text(self, conflict) -> str:
        official = self.catalog.metric(conflict.metric_id)
        actual = ""
        if conflict.actual_metric_id:
            actual = f", which is actually {self.catalog.metric(conflict.actual_metric_id).name}"
        return (
            f'**Warning:** in "{conflict.artifact_title}", "{conflict.label}" is calculated as '
            f"`{conflict.artifact_formula}`{actual}. The official definition of {official.name} is "
            f"`{conflict.official_formula}`. Do not compare these numbers directly."
        )


class LLMExplainer:
    """Rephrases the template draft. The verdict is already fixed; the model only writes the text."""

    def __init__(self, catalog: Catalog, llm: LLMClient, prompts_dir: Path):
        self.template = TemplateExplainer(catalog)
        self.llm = llm
        self.prompts_dir = prompts_dir

    def explain(self, question: ParsedQuestion, decision: Decision, as_of: date) -> str:
        draft = self.template.explain(question, decision, as_of)
        try:
            return self.llm.generate_text(
                render_prompt(
                    self.prompts_dir,
                    "explain",
                    question=question.text,
                    decision=decision.model_dump_json(exclude={"alternatives"}),
                    draft=draft,
                )
            )
        except Exception:
            logger.warning("llm_explain_failed", exc_info=True)
            return draft


def get_explainer(catalog: Catalog, llm: LLMClient | None, prompts_dir: Path) -> Explainer:
    return LLMExplainer(catalog, llm, prompts_dir) if llm else TemplateExplainer(catalog)
