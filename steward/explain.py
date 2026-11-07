from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Protocol

from .catalog import Catalog
from .linking import near_matches
from .llm import LLMClient
from .models import Candidate, Decision, Gap, GapKind, ParsedQuestion, Verdict
from .prompts import render_prompt

logger = logging.getLogger(__name__)

MAX_CONFLICT_LINES = 3  # per answer; the rest is one summary line, the full list is in the Evidence panel

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
        parts += self._conflict_parts(decision)
        return "\n\n".join(parts)

    def _conflict_parts(self, decision: Decision) -> list[str]:
        """Only conflicts in the reports this answer is about, at most MAX_CONFLICT_LINES; the rest is counted."""
        if decision.best is None:  # nothing recommended (CLARIFY, NOT_FEASIBLE): catalog-wide warnings are noise
            return []
        relevant = {c.artifact.id for c in [decision.best, *decision.alternatives] if c}
        mine = [c for c in decision.conflicts if c.artifact_id in relevant][:MAX_CONFLICT_LINES]
        parts = [self._conflict_text(c) for c in mine]
        rest = len(decision.conflicts) - len(mine)
        if rest > 0:
            parts.append(
                f"{rest} other report{'s' if rest != 1 else ''} in the catalog calculate this number differently "
                "from the official definition. The Evidence list below has the details."
            )
        return parts

    def _clarify_text(self, question: ParsedQuestion) -> str:
        """Says what was NOT understood (the word, with a 'did you mean'), not a generic 'which metric'."""
        parts = ["**Please clarify the question.**"]
        parts += question.conflicts
        if question.unmapped_terms:
            shown = []
            for term in question.unmapped_terms[:6]:
                near = near_matches(term, self.catalog)
                shown.append(f'"{term}"' + (f" (did you mean {' or '.join(near)}?)" if near else ""))
            parts.append(
                "I don't recognise " + ", ".join(shown) + ". If it is a real number or product, the domain owner "
                "has to define it first."
            )
        known = [self.catalog.metric(m).name for m in question.metrics] + [
            self.catalog.dimension_value_label(d, v) for d, v in question.filters.items()
        ]
        if known:
            parts.append("Understood so far: " + ", ".join(known) + ".")
        if not question.metrics:
            parts.append("I could not tell which number you want, e.g. net sales, OTIF or stock cover.")
        return " ".join(parts)

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
            return self._clarify_text(question)
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
            actual = f" (it is really {self.catalog.metric(conflict.actual_metric_id).name})"
        return (
            f'**Warning:** in "{conflict.artifact_title}", "{conflict.label}" is not the official {official.name}'
            f"{actual}: it is calculated differently. Do not compare these numbers directly."
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
                    decision=decision.model_dump_json(exclude={"alternatives", "conflicts"}),
                    draft=draft,
                )
            )
        except Exception:
            logger.warning("llm_explain_failed", exc_info=True)
            return draft


def get_explainer(catalog: Catalog, llm: LLMClient | None, prompts_dir: Path) -> Explainer:
    return LLMExplainer(catalog, llm, prompts_dir) if llm else TemplateExplainer(catalog)
