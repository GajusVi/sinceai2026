"""Interview loop (G2): an LLM asks situation questions and fills an Intent; code validates it and stops it.

The model proposes, the code decides: ids outside the dictionary become unmapped_terms (never silently dropped),
and whether to ask another question is Intent.should_stop, not the model's opinion. Without an LLM (or when it
fails) a rules parser plus the fixed questions in prompts/interview.yaml keep the interview working.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from .catalog import Catalog
from .config import AMBIGUOUS_PHRASES
from .intent import MAX_QUESTIONS, Intent, Mode
from .linking import asks_global
from .llm import LLMClient
from .prompts import load_prompt, render_prompt
from .query_parser import RuleBasedParser

logger = logging.getLogger(__name__)

ALL_PHARMA = "All Pharma"
_HANDLED_WORDS = {"worldwide", "world", "global", "globally", "all", "portfolio", "whole", "everything"}
GLOBAL = "Global"


@dataclass
class InterviewState:
    intent: Intent
    turns: list[tuple[str, str]] = field(default_factory=list)  # ("user" | "assistant", text)
    questions_asked: int = 0
    question: str | None = None  # the pending question; None = the interview is finished
    decision_replies: set[int] = field(default_factory=set)  # turn indexes that answer the decision question
    last_asked: str = ""  # conflict | products | markets | metric_ids | decision_supported

    @property
    def done(self) -> bool:
        return self.question is None


class Interviewer:
    def __init__(self, catalog: Catalog, llm: LLMClient | None, prompts_dir: Path):
        self.catalog = catalog
        self.llm = llm
        self.prompts_dir = prompts_dir
        self.bank = load_prompt(prompts_dir, "interview")  # personas + fallback live beside the prompt

    def start(self, text: str, mode: Mode = "novice", conflicts: list[str] | None = None) -> InterviewState:
        state = InterviewState(Intent(text=text, mode=mode, conflicts=list(conflicts or [])), turns=[("user", text)])
        return self._step(state)

    def answer(self, state: InterviewState, reply: str) -> InterviewState:
        state.turns.append(("user", reply))
        return self._step(state)

    # -- one turn ------------------------------------------------------------------------------------------------

    def _step(self, state: InterviewState) -> InterviewState:
        intent = self._llm_intent(state)
        if intent:
            self._fill_gaps(intent, state)
        else:
            intent = self._rules_intent(state)
        state.intent = intent
        if intent.should_stop(state.questions_asked):
            state.question, state.last_asked = None, ""
            return state
        state.last_asked = self._first_open(intent)
        state.question = self._pending_question or self._fallback_question(intent, state.last_asked)
        state.questions_asked += 1
        state.turns.append(("assistant", state.question))
        if state.last_asked == "decision_supported":
            state.decision_replies.add(len(state.turns))  # the next turn is the user's answer
        return state

    _pending_question: str | None = None

    def _llm_intent(self, state: InterviewState) -> Intent | None:
        self._pending_question = None
        if not self.llm:
            return None
        try:
            raw = self.llm.generate_json(
                render_prompt(
                    self.prompts_dir, "interview",
                    dictionary=self._dictionary(), question_bank=self._question_bank(),
                    mode=state.intent.mode, questions_asked=state.questions_asked, max_questions=MAX_QUESTIONS,
                    conflicts="\n".join(state.intent.conflicts) or "none",
                    intent=state.intent.model_dump_json(),
                    conversation="\n".join(f"{who.capitalize()}: {text}" for who, text in state.turns),
                )
            )
            intent = self._validate(raw["intent"], state)
        except Exception:
            logger.warning("llm_interview_failed", exc_info=True)
            return None
        question = raw.get("next_question")
        self._pending_question = question.strip() if isinstance(question, str) and question.strip() else None
        return intent

    def _validate(self, raw: dict, state: InterviewState) -> Intent:
        """Keeps only ids the dictionary knows; everything else is listed in unmapped_terms, not dropped."""
        unmapped = [t for t in raw.get("unmapped_terms", []) if isinstance(t, str)]

        def pick(values, allowed: dict[str, str]) -> list[str]:
            kept: list[str] = []
            for v in values or []:
                canonical = allowed.get(str(v).lower())
                if canonical and canonical not in kept:
                    kept.append(canonical)
                elif not canonical and str(v) not in unmapped:
                    unmapped.append(str(v))
            return kept

        confidence = {
            k: min(1.0, max(0.0, float(v)))
            for k, v in (raw.get("confidence") or {}).items()
            if isinstance(v, (int, float)) and not isinstance(v, bool)
        }
        grain = raw.get("grain") if raw.get("grain") in ("month", "quarter") else "month"
        comparison = raw.get("comparison") if raw.get("comparison") in ("target", "forecast", "prior") else None
        return Intent(
            role=str(raw.get("role") or ""),
            decision_supported=str(raw.get("decision_supported") or ""),
            cadence=str(raw.get("cadence") or ""),
            products=pick(raw.get("products"), self._allowed("product", extra=(ALL_PHARMA,))),
            markets=pick(raw.get("markets"), self._allowed("market", extra=(GLOBAL,), by_label=True)),
            regions=pick(raw.get("regions"), self._allowed("region", by_label=True)),
            metric_ids=pick(raw.get("metric_ids"), {m: m for m in self.catalog.metrics}),
            unmapped_terms=unmapped,
            grain=grain,
            comparison=comparison,
            audience=str(raw.get("audience") or ""),
            conflicts=[c for c in raw.get("conflicts", []) if isinstance(c, str)],
            confidence=confidence,
            mode=state.intent.mode,
            text=state.intent.text,
        )

    # -- offline path --------------------------------------------------------------------------------------------

    def _rules_intent(self, state: InterviewState) -> Intent:
        """No LLM: re-parse everything the user has said, and read a reply to a decision question as the decision."""
        prev = state.intent
        replies = self._scope_replies(state)
        user_text = " ".join(replies)
        last_reply = state.turns[-1][1].lower()
        parser = RuleBasedParser(self.catalog)
        parsed = parser.parse(user_text)
        unmapped: list[str] = []
        for reply in replies:  # a later reply that names a metric restates the request: earlier unknown words go
            part = parser.parse(reply)
            unmapped = part.unmapped_terms if part.metrics else unmapped + part.unmapped_terms
        intent = prev.model_copy(deep=True)
        confidence = dict(prev.confidence)

        if parsed.filters.get("product"):
            intent.products = [self.catalog.dimension_value_label("product", parsed.filters["product"])]
        elif state.last_asked == "products" and re.search(r"\ball\b|portfolio|whole|everything", last_reply):
            intent.products = [ALL_PHARMA]
        if parsed.filters.get("market"):
            intent.markets = [parsed.filters["market"]]
        elif asks_global(user_text) or (state.last_asked == "markets" and re.search(r"world|all markets", last_reply)):
            intent.markets = [GLOBAL]
        if parsed.filters.get("region"):
            intent.regions = [parsed.filters["region"]]
        if parsed.metrics:
            intent.metric_ids = list(parsed.metrics)
        intent.unmapped_terms = [t for t in dict.fromkeys(unmapped) if t.lower() not in _HANDLED_WORDS]
        if state.last_asked == "decision_supported" and state.turns[-1][0] == "user":
            intent.decision_supported = state.turns[-1][1]
        if state.last_asked == "conflict":
            intent.conflicts = []  # the user answered; what they wrote wins

        for name, filled in (
            ("products", intent.products), ("markets", intent.markets or intent.regions),
            ("metric_ids", intent.metric_ids), ("decision_supported", intent.decision_supported),
        ):
            if filled:
                confidence[name] = max(confidence.get(name, 0.0), 0.9)
        intent.confidence = confidence
        return intent

    def _fill_gaps(self, intent: Intent, state: InterviewState) -> None:
        """Some models hand back an empty Intent. The rules parser fills ONLY empty entity fields from the user's own words;
        whatever the model did fill is never overwritten."""
        rules = self._rules_intent(state)
        for name in ("products", "markets", "regions", "metric_ids"):
            if not getattr(intent, name) and getattr(rules, name):
                setattr(intent, name, getattr(rules, name))
                key = "markets" if name == "regions" else name
                intent.confidence[name] = max(intent.confidence.get(name, 0.0), rules.confidence.get(key, 0.9))

    def _scope_replies(self, state: InterviewState) -> list[str]:
        """The user's replies that describe the request. The answer to the decision question is prose, not a request."""
        return [text for i, (who, text) in enumerate(state.turns) if who == "user" and i not in state.decision_replies]

    def _first_open(self, intent: Intent) -> str:
        if intent.conflicts:
            return "conflict"
        missing = intent.missing()
        if missing:
            return {"markets": "markets"}.get(missing[0], missing[0])
        return "decision_supported"

    def _fallback_question(self, intent: Intent, about: str) -> str:
        texts = self.bank["fallback"]
        if about == "conflict":
            return texts["conflict"].format(conflict=intent.conflicts[0])
        return texts[about]

    # -- prompt inputs -------------------------------------------------------------------------------------------

    def _allowed(self, dimension: str, extra: tuple[str, ...] = (), by_label: bool = False) -> dict[str, str]:
        allowed = {e.lower(): e for e in extra}
        dim = self.catalog.dimensions.get(dimension)
        for v in dim.values if dim else []:
            canonical = v.label if dimension == "product" else v.id
            allowed[canonical.lower()] = canonical
            allowed[v.id.lower()] = canonical
            if by_label:
                allowed[v.label.lower()] = canonical
        return allowed

    def _dictionary(self) -> str:
        lines = ["Metrics (id: name; words people use):"]
        lines += [f"- {m.id}: {m.name}; {', '.join(m.synonyms)}" for m in self.catalog.metrics.values()]
        for dim_id, title in (("product", "Products"), ("market", "Markets (id = name)"), ("region", "Regions")):
            dim = self.catalog.dimensions.get(dim_id)
            if dim:
                names = [_dictionary_name(dim_id, v) for v in dim.values]
                lines.append(f"{title}: {', '.join(names)}" + (f", {ALL_PHARMA}" if dim_id == "product" else ""))
        lines.append("Ambiguous words (never guess, ask which number is meant): " + ", ".join(AMBIGUOUS_PHRASES))
        return "\n".join(lines)

    def _question_bank(self) -> str:
        lines = []
        for persona in self.bank["personas"].values():
            lines.append(f"- {persona['who']}:")
            lines += [f'    "{q}"' for q in persona["questions"][:3]]
        return "\n".join(lines)


def _dictionary_name(dimension: str, value) -> str:
    """How a dimension value is shown to the model: product name, "DE = Germany", or the region name."""
    if dimension == "product":
        return value.label
    return f"{value.id} = {value.label}" if dimension == "market" else value.id
