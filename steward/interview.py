"""Interview loop (G2): an LLM asks situation questions and fills an Intent; code validates it and stops it.

The model proposes, the code decides: ids outside the dictionary become unmapped_terms (never silently dropped),
and whether to ask another question is Intent.should_stop, not the model's opinion. Without an LLM (or when it
fails) a rules parser plus the fixed questions in prompts/interview.yaml keep the interview working.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from .catalog import Catalog
from .config import AMBIGUOUS_PHRASES, METRIC_NOUNS, STOPWORDS
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
_CONFIRMS = re.compile(r"\b(yes|yeah|yep|ok|okay|sure|fine|good|right|correct|use|go|perfect|sounds|add|drop|remove|"
                       r"only|just|without|no|nope)\b", re.I)
_FLAG_IT = re.compile(r"\b(flag|owner|define|skip|leave|ignore|forget|never ?mind)\b", re.I)
# Only while the site question is open: typos and bare letters ("Plan B mane", "b") still pick the site.
_SITE_LOOSE = re.compile(r"(?:\bplan(?:t|e)?[\s-]*|^\s*)([abc])\b", re.I)
_ALL_SITES = re.compile(r"\ball\s+(sites|plants|of them)\b|\bevery\s+(site|plant)\b", re.I)
MAX_MISSES = 2  # the same question unanswered twice: use the recommended default and move on, never ask a third time
# What "Skip - use recommended" (or a second miss) fills in, per open question.
DEFAULT_DECISION = "monitor"
DEFAULT_THEME = "business_performance"


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
    options: list[str] = field(default_factory=list)  # one-click answers for the pending question (UI buttons)
    misses: dict[str, int] = field(default_factory=dict)  # question -> replies that did not answer it
    notes: list[str] = field(default_factory=list)  # defaults the interview applied, said back to the user
    unconfirmed_reply: bool = False  # the last reply to "shall I use these?" was about something else
    asked_terms: list[str] = field(default_factory=list)  # the words the "unmapped" question asked about
    asked_choices: list[str] = field(default_factory=list)  # the likely matches offered for them

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
        return self._step(state, asked_before=state.last_asked)

    def finish_with_defaults(self, state: InterviewState) -> InterviewState:
        """"Skip - use recommended": every open question gets its default; the interview ends with a full Intent."""
        intent = state.intent
        for _ in range(8):
            if intent.should_stop(0) and not intent.conflicts:
                break
            about = self._first_open(intent, state)
            self._apply_default(intent, state, about)
        self._close(state)
        state.question, state.last_asked, state.options = None, "", []
        return state

    # -- one turn ------------------------------------------------------------------------------------------------

    def _step(self, state: InterviewState, asked_before: str = "") -> InterviewState:
        state.unconfirmed_reply = False
        intent = self._llm_intent(state)
        if intent:
            self._fill_gaps(intent, state)
        else:
            intent = self._rules_intent(state)
        state.intent = intent
        if asked_before == "unmapped" and state.asked_terms:  # answered (picked, ignored or flagged): never asked again
            if _FLAG_IT.search(state.turns[-1][1]):
                intent.ignored_terms += [t for t in state.asked_terms if t not in intent.ignored_terms]
            intent.unmapped_terms = [t for t in intent.unmapped_terms if t not in state.asked_terms]
        notice = ""
        about = "" if intent.should_stop(state.questions_asked) else self._first_open(intent, state)
        if asked_before and about == asked_before:  # the reply did not answer the question
            state.misses[about] = state.misses.get(about, 0) + 1
            if state.misses[about] >= MAX_MISSES:
                self._apply_default(intent, state, about)
                about = "" if intent.should_stop(state.questions_asked) else self._first_open(intent, state)
            else:
                notice = MISSED.get(about, "I didn't catch that.") + " "
        if not about:
            if not intent.is_complete() or intent.conflicts:  # question budget spent: recommended setup for the rest
                state.notes.append("That's enough questions; I'll use the recommended setup for the rest.")
                self.finish_with_defaults(state)
            self._close(state)
            state.question, state.last_asked, state.options = None, "", []
            return state
        state.last_asked = about
        # The code decides WHAT is asked; the model's wording is used only when it asks about the same thing,
        # and never right after a miss (then the short fixed question with one-click options is clearer).
        llm_text = self._pending_question if self._pending_about == about and not notice else None
        state.question = (" ".join(state.notes) + " " if state.notes else "") + notice + (
            llm_text or self._fallback_question(intent, about)
        )
        state.notes = []
        state.options = self._options(intent, about)
        state.questions_asked += 1  # re-asks count too: the conversation stays short, the cap fills in the rest
        state.turns.append(("assistant", state.question))
        if state.last_asked == "unmapped":
            state.asked_unmapped = True
            state.asked_terms = list(intent.unmapped_terms)
            state.asked_choices = [c for cands in self._near_terms(intent).values() for c in cands]
        if state.last_asked in ("decision_supported", "theme_confirm"):
            state.decision_replies.add(len(state.turns))  # the next turn answers it: prose, not request text
        return state

    _pending_question: str | None = None
    _pending_about: str = ""

    def _llm_intent(self, state: InterviewState) -> Intent | None:
        self._pending_question, self._pending_about = None, ""
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
        self._pending_about = str(raw.get("asks_about") or "")
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
            unmapped_terms=[t for t in unmapped if t not in state.intent.ignored_terms],
            ignored_terms=list(state.intent.ignored_terms),
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
            if state.last_asked == "theme_confirm" and state.turns[-1][0] == "user" and not state.unconfirmed_reply:
                state.theme_confirmed = True
            if named or state.theme_confirmed:
                intent.confidence["metric_ids"] = max(intent.confidence.get("metric_ids", 0.0), 0.9)
            if state.theme_confirmed:  # the confirm question named the not-governed gaps; the user accepted them
                gaps = " ".join(theme.get("not_governed") or []).lower()
                intent.unmapped_terms = [t for t in intent.unmapped_terms if t.lower() not in gaps]
            else:
                intent.confidence["metric_ids"] = min(intent.confidence.get("metric_ids", 0.0), THEME_CONFIDENCE)
        known = {n.lower() for n in self._scope_names()} | self._market_ids()
        intent.unmapped_terms = [
            t for t in intent.unmapped_terms
            if t.lower() not in _SITE_TOKENS and t.lower() not in STOPWORDS and t not in intent.ignored_terms
            and t.lower() not in known
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

    # -- presets, defaults and closing -----------------------------------------------------------------------------

    def _options(self, intent: Intent, about: str) -> list[str]:
        """One-click answers in the user's words. Each is a reply the offline parser understands."""
        if about == "sites":
            named = [x for x in self.sites if x != "External-CMO"]
            return named + (["Contract manufacturer"] if "External-CMO" in self.sites else []) + ["All sites"]
        if about == "products":
            dim = self.catalog.dimensions.get("product")
            return ["All medicines"] + [v.label for v in (dim.values if dim else [])][:4]
        if about == "markets":
            return ["Worldwide", "EMEA", "North America", "Asia Pacific", "Latin America"]
        if about == "theme_confirm":
            extra = "Add net sales" if "net_sales" not in intent.metric_ids else "Add on-time in-full"
            return ["Yes, use these", extra]
        if about == "metric_ids":
            return [_capital(t["label"]) for t in self.themes.values()]
        if about == "unmapped":
            near = [c for cands in self._near_terms(intent).values() for c in cands]
            return list(dict.fromkeys(near))[:4] + ["Ignore it"] if near else ["Ignore it", "Flag for data owner"]
        if about == "decision_supported":
            return ["Board update", "Weekly review", "Decide on an action", "Keep an eye on it"]
        if about == "conflict":
            return ["What I wrote is right"]
        return []

    def _apply_default(self, intent: Intent, state: InterviewState, about: str) -> None:
        """The recommended answer to one open question (used by Skip and after a second miss). Said back once."""
        if about == "sites":
            intent.sites = []
            intent.products, intent.markets = [ALL_PHARMA], [GLOBAL]
            for k in ("products", "markets"):
                intent.confidence[k] = 0.9
            state.notes.append("I'll cover all sites; you can narrow it down in the dashboard.")
            state.misses["sites_done"] = 1  # do not ask "which site?" again
        elif about == "products":
            intent.products, intent.confidence["products"] = [ALL_PHARMA], 0.9
            state.notes.append("I'll include all medicines.")
        elif about == "markets":
            intent.markets, intent.confidence["markets"] = [GLOBAL], 0.9
            state.notes.append("I'll show all markets.")
        elif about in ("theme_confirm", "metric_ids"):
            if not intent.metric_ids:
                intent.theme = intent.theme or DEFAULT_THEME
                intent.metric_ids = [m for m in self.themes[intent.theme]["metrics"] if m in self.catalog.metrics]
            intent.confidence["metric_ids"], state.theme_confirmed = 0.9, True
        elif about == "unmapped":
            state.asked_unmapped = True
            intent.ignored_terms += [t for t in intent.unmapped_terms if t not in intent.ignored_terms]
            intent.unmapped_terms = []
        elif about == "decision_supported":
            intent.decision_supported = intent.decision_supported or DEFAULT_DECISION
            intent.confidence["decision_supported"] = 0.9
        elif about == "conflict":
            intent.conflicts = []  # the text the user wrote wins

    def _close(self, state: InterviewState) -> None:
        """End of the interview: words still unplaced never block the result. They are kept on the Intent as
        ignored_terms and shown as a note next to the dashboard ("not used: ...")."""
        intent = state.intent
        intent.ignored_terms += [t for t in intent.unmapped_terms if t not in intent.ignored_terms]
        intent.unmapped_terms = []

    def _near_terms(self, intent: Intent) -> dict[str, list[str]]:
        """Unplaced words that look like a place or a medicine ("America", "Germny", "Xareltoo"): worth one question
        with the likely matches as buttons. Anything else ("yo mom", "thumbs up") is quietly ignored at the end."""
        out: dict[str, list[str]] = {}
        names = self._scope_names()
        for term in intent.unmapped_terms:
            low = term.lower()
            if len(low) < 3 or low in STOPWORDS:
                continue
            cands = [
                n for n in names if low in n.lower().split() or SequenceMatcher(None, low, n.lower()).ratio() >= 0.8
            ]
            if cands:
                out[term] = cands[:3]
        return out

    def _scope_names(self) -> list[str]:
        names: list[str] = []
        for dim_id in ("region", "market", "product"):
            dim = self.catalog.dimensions.get(dim_id)
            for v in dim.values if dim else []:
                names.append(v.label if dim_id != "region" else v.id)
        return list(dict.fromkeys(names))

    def _market_ids(self) -> set[str]:
        dim = self.catalog.dimensions.get("market")
        return {v.id.lower() for v in (dim.values if dim else [])}

    def _scope_in(self, reply: str) -> tuple[list[str], list[str]]:
        """Markets and regions named in a short answer: ids ("DE"), names ("Germany"), regions ("North America")."""
        markets, regions = [], []
        words = re.findall(r"[A-Za-z]+", reply)
        low = reply.lower()
        for dim_id, bucket in (("market", markets), ("region", regions)):
            dim = self.catalog.dimensions.get(dim_id)
            for v in dim.values if dim else []:
                if (dim_id == "market" and v.id in words) or v.label.lower() in low or (
                    dim_id == "region" and v.id.lower() in low
                ):
                    bucket.append(v.id)
        return markets, regions

    def _measure_like(self, intent: Intent) -> bool:
        words = " ".join(intent.unmapped_terms).lower().split()
        return any(w in METRIC_NOUNS for w in words)

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
        if parsed.filters.get("region") and parsed.filters["region"] not in intent.regions:
            intent.regions = intent.regions + [parsed.filters["region"]] if prev.regions else [parsed.filters["region"]]
        if state.last_asked in ("markets", "unmapped") and state.turns[-1][0] == "user":
            answer = state.turns[-1][1]
            if state.last_asked == "unmapped" and re.search(r"\b(both|all|each|every)\b", answer, re.I):
                answer = " ".join(state.asked_choices)  # "both" = every match offered
            markets, regions = self._scope_in(answer)  # "DE", "North America": added to what was said
            intent.markets = list(dict.fromkeys([m for m in intent.markets if m != GLOBAL] + markets)) or intent.markets
            intent.regions = list(dict.fromkeys(intent.regions + regions))
        if parsed.metrics and not state.theme_confirmed:  # after "is that the right picture?" the answer stands
            intent.metric_ids = list(parsed.metrics)
        intent.unmapped_terms = [t for t in dict.fromkeys(unmapped) if t.lower() not in _HANDLED_WORDS]
        if state.last_asked == "decision_supported" and state.turns[-1][0] == "user":
            intent.decision_supported = state.turns[-1][1]
        if state.last_asked == "conflict":
            intent.conflicts = []  # the user answered; what they wrote wins
        sites = self._sites_in(user_text)
        if state.last_asked == "sites" and not sites:
            loose = _SITE_LOOSE.search(last_reply)
            if loose and f"Plant-{loose.group(1).upper()}" in self.sites:
                sites = [f"Plant-{loose.group(1).upper()}"]
            elif _ALL_SITES.search(last_reply):
                self._apply_default(intent, state, "sites")
        if sites:
            intent.sites = sites
        if state.last_asked == "metric_ids":
            picked = next((k for k, t in self.themes.items() if t["label"].lower() in last_reply), "")
            if picked:  # a one-click theme pick is its own confirmation
                intent.theme, state.theme_confirmed = picked, True
                intent.metric_ids = [m for m in self.themes[picked]["metrics"] if m in self.catalog.metrics]
        if state.last_asked == "theme_confirm" and state.turns[-1][0] == "user":
            if _CONFIRMS.search(last_reply) or RuleBasedParser(self.catalog).parse(last_reply).metrics:
                intent.metric_ids = self._adjust(prev.metric_ids, last_reply)
            else:  # "adding a shift": not an answer to "shall I use these?", but it is what the numbers are for
                state.theme_confirmed = False
                state.unconfirmed_reply = True
                scope_words = (self._sites_in(last_reply) or _SITE_LOOSE.search(last_reply)
                               or parser.parse(last_reply).filters)
                if not intent.decision_supported and not scope_words:
                    intent.decision_supported = state.turns[-1][1]

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
        for name in ("products", "markets", "regions", "sites", "metric_ids", "decision_supported"):
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
        site_theme = intent.theme == "plant_efficiency" and not intent.markets and not intent.regions
        if (not intent.sites and not intent.products and "sites_done" not in state.misses and self.sites
                and (self._mentions_site(state) or site_theme)):
            return "sites"  # "this plant": which one? Its scope replaces the product and market questions
        missing = intent.missing()
        if missing and missing[0] != "decision_supported":
            if missing[0] == "metric_ids" and intent.theme and intent.metric_ids:
                return "theme_confirm"
            return missing[0]
        worth_asking = self._measure_like(intent) or self._near_terms(intent)
        if worth_asking and not state.asked_unmapped and intent.mode != "expert":
            return "unmapped"  # once, and only for words that look like a number ("batch yield"); junk is ignored
        return "decision_supported"

    def _fallback_question(self, intent: Intent, about: str) -> str:
        texts = self.bank["fallback"]
        if about == "conflict":
            return texts["conflict"].format(conflict=intent.conflicts[0])
        if about == "unmapped" and self._near_terms(intent):
            term, cands = next(iter(self._near_terms(intent).items()))
            return texts["near"].format(term=term, choices=_and_list(cands).replace(" and ", " or "))
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


MISSED = {
    "theme_confirm": "Noted.",
    "sites": "I didn't catch a site in that.",
    "products": "I didn't catch a medicine in that.",
    "markets": "I didn't catch a country or region in that.",
    "metric_ids": "I didn't catch which numbers you mean.",
    "decision_supported": "I didn't quite get what it's for.",
}


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
