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
from .config import AMBIGUOUS_PHRASES, STOPWORDS
from .intent import MAX_QUESTIONS, Intent, Mode
from .linking import asks_global
from .llm import LLMClient
from .prompts import load_prompt, render_prompt
from .query_parser import RuleBasedParser

logger = logging.getLogger(__name__)

ALL_PHARMA = "All Pharma"
_HANDLED_WORDS = {"worldwide", "world", "global", "globally", "all", "portfolio", "whole", "everything"}
GLOBAL = "Global"
THEME_CONFIDENCE = 0.6  # proposed by a goal theme, not said by the user: below CONFIDENCE_MIN, so it must be confirmed
# Words that point at a supply site. Named: "Plant B", "plant-a", "the CMO". Unnamed: "this plant", "our site".
_SITE_NAMED = (
    (re.compile(r"\bplant[\s-]?([abc])\b", re.I), lambda m: f"Plant-{m.group(1).upper()}"),
    (re.compile(r"\b(cmo|contract manufactur\w*|external(ly)?[\s-](site|plant|manufactur\w*|cmo))\b", re.I),
     lambda m: "External-CMO"),
)
_SITE_WORD = re.compile(r"\b(plants?|sites?|factor(y|ies)|facilit(y|ies)|manufacturing|cmo)\b", re.I)
_SITE_TOKENS = {"plant", "plants", "site", "sites", "factory", "factories", "facility", "facilities", "manufacturing",
                "cmo", "external", "contract", "manufacturer", "plant-a", "plant-b", "plant-c", "a", "b", "c"}
_CONFIRM_ADD = re.compile(r"\b(add|also|plus|include|and)\b", re.I)
_CONFIRM_DROP = re.compile(r"\b(drop|remove|without|skip|not|no)\b", re.I)
_CONFIRM_ONLY = re.compile(r"\b(only|just|instead)\b", re.I)
_FLAG_IT = re.compile(r"\b(flag|owner|define|skip|leave|ignore|forget|never ?mind)\b", re.I)


@dataclass
class InterviewState:
    intent: Intent
    turns: list[tuple[str, str]] = field(default_factory=list)  # ("user" | "assistant", text)
    questions_asked: int = 0
    question: str | None = None  # the pending question; None = the interview is finished
    decision_replies: set[int] = field(default_factory=set)  # turn indexes that answer the decision question
    last_asked: str = ""  # conflict | sites | products | markets | metric_ids | theme_confirm | decision_supported
    theme_confirmed: bool = False  # the user answered "is that the right picture?" (or named numbers themselves)
    asked_unmapped: bool = False  # the one question about words we could not place has been asked

    @property
    def done(self) -> bool:
        return self.question is None


class Interviewer:
    def __init__(self, catalog: Catalog, llm: LLMClient | None, prompts_dir: Path):
        self.catalog = catalog
        self.llm = llm
        self.prompts_dir = prompts_dir
        self.bank = load_prompt(prompts_dir, "interview")  # personas + fallback live beside the prompt
        self.themes: dict[str, dict] = self.bank.get("themes", {})
        self.sites = _supply_sites(catalog)  # [] on the sample catalog

    def start(self, text: str, mode: Mode = "novice", conflicts: list[str] | None = None) -> InterviewState:
        state = InterviewState(Intent(text=text, mode=mode, conflicts=list(conflicts or [])), turns=[("user", text)])
        return self._step(state)

    def answer(self, state: InterviewState, reply: str) -> InterviewState:
        if state.last_asked == "unmapped" and _FLAG_IT.search(reply):
            state.decision_replies.add(len(state.turns))  # "flag it": the words stay unmapped, the reply is not scope
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
        state.last_asked = self._first_open(intent, state)
        state.question = self._pending_question or self._fallback_question(intent, state.last_asked)
        state.questions_asked += 1
        state.turns.append(("assistant", state.question))
        if state.last_asked == "unmapped":
            state.asked_unmapped = True
        if state.last_asked in ("decision_supported", "theme_confirm"):
            state.decision_replies.add(len(state.turns))  # the next turn answers it: prose, not request text
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
                    dictionary=self._dictionary(), question_bank=self._question_bank(), themes=self._themes_text(),
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
        theme = raw.get("theme") if raw.get("theme") in self.themes else ""
        site_ids = {x.lower(): x for x in self.sites}
        site_ids.update({x.lower().replace("-", " "): x for x in self.sites})
        grain = raw.get("grain") if raw.get("grain") in ("month", "quarter") else "month"
        comparison = raw.get("comparison") if raw.get("comparison") in ("target", "forecast", "prior") else None
        return Intent(
            role=str(raw.get("role") or ""),
            decision_supported=str(raw.get("decision_supported") or ""),
            cadence=str(raw.get("cadence") or ""),
            products=pick(raw.get("products"), self._allowed("product", extra=(ALL_PHARMA,))),
            markets=pick(raw.get("markets"), self._allowed("market", extra=(GLOBAL,), by_label=True)),
            regions=pick(raw.get("regions"), self._allowed("region", by_label=True)),
            sites=pick(raw.get("sites"), site_ids),
            theme=theme,
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

    # -- goal themes and sites (both paths) ------------------------------------------------------------------------

    def _apply_theme(self, intent: Intent, state: InterviewState) -> None:
        """A goal word ("efficiency") is answered with the theme's governed numbers, proposed at THEME_CONFIDENCE.
        They count as confirmed only once the user has answered the confirm question or named numbers themselves.
        Goal and site words are understood, so they never stay in unmapped_terms (that would force CLARIFY)."""
        text = " ".join(self._scope_replies(state))
        if not intent.theme:
            intent.theme = self._theme_of(text)
        if intent.theme in ("", "business_performance") and self._mentions_site(state) and not intent.products:
            intent.theme = "plant_efficiency" if "plant_efficiency" in self.themes else intent.theme
        theme = self.themes.get(intent.theme)
        if theme:  # any goal word is understood (a site question may have moved "doing" to plant_efficiency)
            words = {w.lower() for t in self.themes.values() for w in t["words"]}
            intent.unmapped_terms = [t for t in intent.unmapped_terms if t.lower() not in words]
            if not intent.metric_ids:
                intent.metric_ids = [m for m in theme["metrics"] if m in self.catalog.metrics]
            named = RuleBasedParser(self.catalog).parse(" ".join(self._scope_replies(state))).metrics
            if state.last_asked == "theme_confirm" and state.turns[-1][0] == "user":
                state.theme_confirmed = True
            if named or state.theme_confirmed:
                intent.confidence["metric_ids"] = max(intent.confidence.get("metric_ids", 0.0), 0.9)
            if state.theme_confirmed:  # the confirm question named the not-governed gaps; the user accepted them
                gaps = " ".join(theme.get("not_governed") or []).lower()
                intent.unmapped_terms = [t for t in intent.unmapped_terms if t.lower() not in gaps]
            else:
                intent.confidence["metric_ids"] = min(intent.confidence.get("metric_ids", 0.0), THEME_CONFIDENCE)
        intent.unmapped_terms = [
            t for t in intent.unmapped_terms if t.lower() not in _SITE_TOKENS and t.lower() not in STOPWORDS
        ]

    def _theme_of(self, text: str) -> str:
        low = text.lower()
        for key, theme in self.themes.items():
            for word in theme["words"]:
                if (" " in word or "-" in word) and word in low or re.search(rf"\b{re.escape(word)}\b", low):
                    return key
        return ""

    def _sites_in(self, text: str) -> list[str]:
        found: list[str] = []
        for pattern, name in _SITE_NAMED:
            for m in pattern.finditer(text):
                site = name(m)
                if site in self.sites and site not in found:
                    found.append(site)
        return found

    def _mentions_site(self, state: InterviewState) -> bool:
        return bool(self.sites) and bool(_SITE_WORD.search(" ".join(self._scope_replies(state))))

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
        if parsed.metrics and not state.theme_confirmed:  # after "is that the right picture?" the answer stands
            intent.metric_ids = list(parsed.metrics)
        intent.unmapped_terms = [t for t in dict.fromkeys(unmapped) if t.lower() not in _HANDLED_WORDS]
        if state.last_asked == "decision_supported" and state.turns[-1][0] == "user":
            intent.decision_supported = state.turns[-1][1]
        if state.last_asked == "conflict":
            intent.conflicts = []  # the user answered; what they wrote wins
        sites = self._sites_in(user_text)
        if sites:
            intent.sites = sites
        if state.last_asked == "theme_confirm" and state.turns[-1][0] == "user":
            intent.metric_ids = self._adjust(prev.metric_ids, last_reply)

        for name, filled in (
            ("products", intent.products), ("markets", intent.markets or intent.regions), ("sites", intent.sites),
            ("metric_ids", intent.metric_ids), ("decision_supported", intent.decision_supported),
        ):
            if filled:
                confidence[name] = max(confidence.get(name, 0.0), 0.9)
        intent.confidence = confidence
        self._apply_theme(intent, state)
        return intent

    def _adjust(self, current: list[str], reply: str) -> list[str]:
        """Offline reading of the answer to "is that the right picture?": "yes" keeps the bundle; "only X" replaces it;
        "drop X" removes X; "add X" (or naming X) adds it."""
        named = list(RuleBasedParser(self.catalog).parse(reply).metrics)
        if not named:
            return current
        if _CONFIRM_ONLY.search(reply):
            return named
        if _CONFIRM_DROP.search(reply) and not _CONFIRM_ADD.search(reply):
            return [m for m in current if m not in named] or current
        return current + [m for m in named if m not in current]

    def _fill_gaps(self, intent: Intent, state: InterviewState) -> None:
        """Some models hand back an empty Intent. The rules parser fills ONLY empty entity fields from the user's
        own words; whatever the model did fill is never overwritten."""
        rules = self._rules_intent(state)
        for name in ("products", "markets", "regions", "sites", "metric_ids"):
            if not getattr(intent, name) and getattr(rules, name):
                setattr(intent, name, getattr(rules, name))
                key = "markets" if name == "regions" else name
                intent.confidence[name] = max(intent.confidence.get(name, 0.0), rules.confidence.get(key, 0.9))
        self._apply_theme(intent, state)

    def _scope_replies(self, state: InterviewState) -> list[str]:
        """The user's replies that describe the request. The answer to the decision question is prose, not a request."""
        return [text for i, (who, text) in enumerate(state.turns) if who == "user" and i not in state.decision_replies]

    def _first_open(self, intent: Intent, state: InterviewState) -> str:
        if intent.conflicts:
            return "conflict"
        if not intent.sites and not intent.products and self._mentions_site(state):
            return "sites"  # "this plant": which one? Its scope replaces the product and market questions
        missing = intent.missing()
        if missing and missing[0] != "decision_supported":
            if missing[0] == "metric_ids" and intent.theme and intent.metric_ids:
                return "theme_confirm"
            return missing[0]
        if intent.unmapped_terms and not state.asked_unmapped and intent.mode != "expert":
            return "unmapped"  # once: offer governed numbers or flag it; what stays unmapped goes to the engine
        return "decision_supported"

    def _fallback_question(self, intent: Intent, about: str) -> str:
        texts = self.bank["fallback"]
        if about == "conflict":
            return texts["conflict"].format(conflict=intent.conflicts[0])
        if about == "unmapped":
            ids = intent.metric_ids or self.themes.get(intent.theme, {}).get("metrics", [])
            names = [self.catalog.metrics[m].name.lower() for m in ids if m in self.catalog.metrics]
            fallback = "sales, on-time delivery or stock cover"
            numbers = _and_list(names[:3]).replace(" and ", " or ") if names else fallback
            return texts["unmapped"].format(terms=", ".join(intent.unmapped_terms), numbers=numbers)
        if about == "theme_confirm":
            theme = self.themes[intent.theme]
            names = [self.catalog.metrics[m].name.lower() for m in intent.metric_ids if m in self.catalog.metrics]
            numbers = _and_list(names)
            gaps = theme.get("not_governed") or []
            gap_text = texts["theme_gaps"].format(gaps=_capital(_and_list(gaps))) if gaps else ""
            return texts["theme_confirm"].format(label=theme["label"], numbers=numbers, gaps=gap_text)
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
        if self.sites:
            lines.append("Sites (plants and the external contract manufacturer): " + ", ".join(self.sites))
        lines.append("Ambiguous words (never guess, ask which number is meant): " + ", ".join(AMBIGUOUS_PHRASES))
        return "\n".join(lines)

    def _themes_text(self) -> str:
        lines = []
        for key, t in self.themes.items():
            gaps = ", ".join(t.get("not_governed") or []) or "none"
            lines.append(
                f"- {key} ({t['label']}): words {', '.join(t['words'])}; numbers {', '.join(t['metrics'])} "
                f"({t['why']}); not governed: {gaps}"
            )
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


def _and_list(items: list[str]) -> str:
    return ", ".join(items[:-1]) + f" and {items[-1]}" if len(items) > 1 else (items[0] if items else "")


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def _supply_sites(catalog: Catalog) -> list[str]:
    """Supply sites of the data pack (Supply_Operations.supply_source). The sample catalog has none."""
    from .linking import kpi_index

    if not kpi_index(catalog)[0]:
        return []
    from .semantic import load_frames

    return sorted(load_frames()["fact_supply"]["supply_source"].dropna().unique().tolist())
