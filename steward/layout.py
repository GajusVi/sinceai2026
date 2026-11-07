"""Dynamic layout (decide side): the order the viewer reads the dashboard in, and the visual used for each step.

The page is a story, one step after the other: the answer (cards) -> when it moved (trend) -> where it comes from
(breakdown) -> what to act on (exceptions). The LLM proposes the sequence from a MENU of visuals that the rules in
specbuild._menu already allow; code validates the proposal and falls back to the deterministic template page.

Rails (Gajus 1107-163850, agreed with Margiris):
- verdict, numbers and measures stay code: the LLM only picks ids from the menu, so it cannot add a measure, a type,
  a threshold or a title; the text it writes (a one-line question per step) is rejected if it contains a digit or an id;
- the role sets the envelope (how much, which types), the LLM orders inside it;
- every measure the template would show as a card stays on the page (gaps included: a gap is a labelled gap card),
  cards come first (the answer first), caps from lint FOCUS hold;
- no LLM, a transport error or a rejected proposal -> the template page for that role (make demo works offline).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .spec import Page, Visual

logger = logging.getLogger(__name__)
PROMPT = "layout"
PROMPT_FILE = "prompts/layout.yaml"
MAX_QUESTION = 110
MAX_REASON = 240
_DIGIT = re.compile(r"\d")
_RECORD_ID = re.compile(r"\b(?:KPI|AST|MDL|REQ|USR)-", re.I)
# The question shows as a subtitle (the title is code): neutral wording only, no alarm or judgement words.
_LOADED = re.compile(r"!|\b(?:collaps\w*|crash\w*|disaster\w*|terribl\w*|awful|plummet\w*|soar\w*|fail\w*|panic\w*)\b", re.I)
_CACHE: dict[str, dict] = {}
# Validated proposals also persist on disk (any client), so a demo replays them offline and a 429 costs nothing for a
# page seen before. tools/warm_layout.py (make warm-layout) fills it for the demo questions x roles. Tests: tmp dir.
CACHE_DIR = Path(os.environ.get("STEWARD_LAYOUT_CACHE", Path(__file__).with_name("layout_cache")))


def _disk_get(key: str) -> dict | None:
    try:
        return json.loads((CACHE_DIR / f"{key[:24]}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _disk_put(key: str, raw: dict) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{key[:24]}.json").write_text(json.dumps(raw, indent=1, sort_keys=True), encoding="utf-8")
    except OSError as exc:  # a read-only checkout still works, it just calls the model again next time
        logger.warning("layout_cache_write: %s", exc)


# OVERVIEW pages (Donatas, Gajus OK 1108-011104): the rules every OVERVIEW page must pass, the deterministic template
# in specbuild._overview_page and any future LLM proposal alike. A failure -> today's template.
OVERVIEW_TYPES = frozenset({"kpi_strip", "line", "bar", "bullet", "diverging_bar", "stacked_100", "table"})
OVERVIEW_SPANS = frozenset({3, 4, 6, 8, 12})
OVERVIEW_MAX_TILES, OVERVIEW_MAX_CHARTS, OVERVIEW_MAX_TABLES = 8, 6, 1


def validate_overview(page: Page, known: set[str], gaps: set[str]) -> list[str]:
    """Problems with an OVERVIEW page, empty = valid: known visual types, governed measures only, gaps only as tiles,
    one strip of <= 8 tiles, <= 6 charts, <= 1 table, every visual on a row with a span, spans sum to 12 per row."""
    problems: list[str] = []
    rows: dict[int, int] = {}
    strips = charts = tables = 0
    for v in page.visuals:
        if v.type not in OVERVIEW_TYPES:
            problems.append(f"{v.title}: unknown visual type {v.type!r}")
        if unknown := [n for n in v.measures if n not in known]:
            problems.append(f"{v.title}: not a governed measure of this spec: {', '.join(unknown)}")
        if v.type != "kpi_strip" and any(n in gaps for n in v.measures):
            problems.append(f"{v.title}: a gap can only be a labelled tile")
        span, row = getattr(v, "span", None), getattr(v, "row", None)
        if span not in OVERVIEW_SPANS or not isinstance(row, int) or row < 1:
            problems.append(f"{v.title}: needs a row and a span of 3, 4, 6, 8 or 12")
        else:
            rows[row] = rows.get(row, 0) + span
        strips += v.type == "kpi_strip"
        tables += v.type == "table"
        charts += v.type not in ("kpi_strip", "table")
        if v.type == "kpi_strip" and len(v.measures) > OVERVIEW_MAX_TILES:
            problems.append(f"{v.title}: {len(v.measures)} tiles, the limit is {OVERVIEW_MAX_TILES}")
    problems += [f"row {r}: spans sum to {total}, not 12" for r, total in sorted(rows.items()) if total != 12]
    if strips != 1:
        problems.append(f"{strips} KPI strips; an overview has exactly one")
    if charts > OVERVIEW_MAX_CHARTS:
        problems.append(f"{charts} charts; the limit is {OVERVIEW_MAX_CHARTS}")
    if tables > OVERVIEW_MAX_TABLES:
        problems.append(f"{tables} tables; the limit is {OVERVIEW_MAX_TABLES}")
    return problems


class LayoutError(ValueError):
    """The proposal broke a rule; the template page is used instead."""


@dataclass(frozen=True)
class Option:
    """One entry of the layout menu: a visual the rules allow. `id` is "<type>:<kpi id>"."""

    id: str
    visual: Visual
    kpi_id: str
    feasible: bool = True  # False = a gap card


@dataclass(frozen=True)
class Envelope:
    """What a role may be shown. Code decides this; the LLM never widens it."""

    max_visuals: int
    max_cards: int
    types: frozenset[str]
    note: str


ALL_TYPES = frozenset({"card", "line", "bar", "table"})
ENVELOPES: dict[str, Envelope] = {
    "worker": Envelope(4, 3, frozenset({"card", "line"}), "a glance: the answer and when it moved, no digging"),
    "management": Envelope(6, 4, ALL_TYPES, "the full story for the own plant, without extra detail"),
    "builder": Envelope(7, 4, ALL_TYPES, "the full story; governance detail sits in the footer"),
}


def envelope_for(role: str | None) -> Envelope:
    """Fails closed: no viewer or an unknown role gets the narrowest envelope (worker), never the builder's."""
    return ENVELOPES.get(role or "", ENVELOPES["worker"])


def fit(template: Page, env: Envelope, gaps: list[Visual] | tuple = ()) -> Page:
    """The deterministic page for a role: the template, cut to the envelope (builder: unchanged). A gap card always
    stays (an infeasible KPI is a labelled gap, never silently dropped); what the cut removes is listed by hidden()."""
    must = [v for v in template.visuals if v.type == "card" and v in gaps]
    cards = [v for v in template.visuals if v.type == "card" and v not in gaps][: max(0, env.max_cards - len(must))]
    rest = [v for v in template.visuals if v.type != "card" and v.type in env.types]
    head = [v for v in template.visuals if v in cards or v in must]  # template order
    return template.model_copy(update={"visuals": head + rest[: max(0, env.max_visuals - len(head))]})


def hidden(template: Page, page: Page) -> list[str]:
    """Titles of the measures the template shows as cards that this page does not show (the role cut them)."""
    shown = {m for v in page.visuals for m in v.measures}
    return [m for v in template.visuals if v.type == "card" for m in v.measures if m not in shown]


def _clean_text(text: object, default: str, limit: int = MAX_QUESTION) -> str:
    """A model-written sentence, or `default` when it carries a digit, a record id or is too long."""
    text = " ".join(str(text or "").split())
    if not text or len(text) > limit or _DIGIT.search(text) or _RECORD_ID.search(text) or _LOADED.search(text):
        return default
    return text


def _step_fields(position: int, question: str) -> dict:
    """purpose always; Visual.step and Visual.question (Gajus OK, Martynas adds them to spec.py) once they exist."""
    fields = {"purpose": question, "step": position, "question": question}
    return {k: v for k, v in fields.items() if k in Visual.model_fields}


def plan(raw: object, options: list[Option], base: Page, env: Envelope) -> tuple[Page, str]:
    """Validate a proposal {"steps": [{"id", "question"}], "reason"} -> (page, reason). Raises LayoutError."""
    if not isinstance(raw, dict) or not isinstance(raw.get("steps"), list) or not raw["steps"]:
        raise LayoutError("no steps")
    menu = {o.id: o for o in options}
    chosen: list[tuple[Option, str]] = []
    seen: set[str] = set()
    for step in raw["steps"]:
        oid = step.get("id") if isinstance(step, dict) else None
        option = menu.get(oid) if isinstance(oid, str) else None
        if option is None or oid in seen or option.visual.type not in env.types:
            continue  # unknown id, repeat or a type this role may not see: dropped, never invented
        seen.add(oid)
        chosen.append((option, _clean_text(step.get("question"), option.visual.purpose)))
    if not chosen:
        raise LayoutError("no valid step")
    required = [o for o in options if o.visual.type == "card" and o.visual in base.visuals]
    cards = [(o, q) for o, q in chosen if o.visual.type == "card"]
    rest = [(o, q) for o, q in chosen if o.visual.type != "card"]
    must = {o.id for o in required}
    room = env.max_cards - len(required)
    kept, extra = [], 0
    for o, q in cards:  # a requested measure always stays; other cards only while there is room
        if o.id in must:
            kept.append((o, q))
        elif extra < room:
            kept.append((o, q))
            extra += 1
    have = {o.id for o, _ in kept}
    kept += [(o, o.visual.purpose) for o in required if o.id not in have]  # forced: answer for every asked measure
    ordered = kept + rest[: max(0, env.max_visuals - len(kept))]  # forced cards are never cut by the cap
    visuals = [o.visual.model_copy(update=_step_fields(n, q)) for n, (o, q) in enumerate(ordered, 1)]
    reason = _clean_text(raw.get("reason"), "", MAX_REASON)
    return base.model_copy(update={"visuals": visuals}), reason


class Layouter:
    """Arranges one page for one viewer. `info` (layout_source, model, prompt, role, ...) goes into spec.provenance."""

    def __init__(self, llm=None, prompts_dir: Path | None = None, user=None):
        self.llm = llm
        self.prompts_dir = prompts_dir or Path("prompts")
        self.role = getattr(user, "role", None) if getattr(user, "role", None) in ENVELOPES else "worker"
        self.user = user
        self.info: dict[str, str] = {}

    def arrange(self, options: list[Option], template: Page, intent) -> Page:
        env = envelope_for(self.role)
        base = fit(template, env, [o.visual for o in options if not o.feasible])
        self.info = {"layout_source": "template", "model": "", "prompt": "", "layout_role": self.role}
        page = base if self.llm is None or len(options) < 2 else self._llm_page(options, base, env, intent)
        cut = hidden(template, page)
        if cut:  # never a silent drop: the UI shows "Not shown for your role: ..."
            self.info["layout_hidden"] = "; ".join(cut)
        return page

    def _llm_page(self, options: list[Option], base: Page, env: Envelope, intent) -> Page:
        try:
            key, raw = self._propose(options, base, env, intent)
            page, reason = plan(raw, options, base, env)
            if key not in _CACHE:
                _disk_put(key, raw)
            _CACHE[key] = raw  # only a proposal that passed validation is reused
        except Exception as exc:  # transport error, bad JSON or a broken rule: the template page, never a crash
            logger.warning("layout_fallback: %s", exc)
            self.info["layout_fallback"] = str(exc)[:160]
            return base
        self.info.update(layout_source="llm", model=str(getattr(self.llm, "model", "")), prompt=PROMPT_FILE)
        if reason:
            self.info["layout_reason"] = reason
        return page

    def _propose(self, options: list[Option], base: Page, env: Envelope, intent) -> tuple[str, dict]:
        from .prompts import render_prompt

        prompt = render_prompt(
            self.prompts_dir,
            PROMPT,
            request=getattr(intent, "text", "") or "(none)",
            viewer=self._viewer(),
            scope=self._scope(intent),
            limits=(
                f"{env.max_visuals} visuals, {env.max_cards} cards, types: {', '.join(sorted(env.types))}; {env.note}"
            ),
            menu="\n".join(self._line(o, o.visual in base.visuals) for o in options),
        )
        key = hashlib.sha256(prompt.encode()).hexdigest()
        if key not in _CACHE and (hit := _disk_get(key)) is not None:
            _CACHE[key] = hit
            self.info["layout_cache"] = "disk"
        return key, _CACHE[key] if key in _CACHE else self.llm.generate_json(prompt)

    def _viewer(self) -> str:
        u = self.user
        if u is None:
            return "unknown viewer: keep it to a glance"
        dept = f", department {u.department}" if getattr(u, "department", None) else ""
        return f"{u.role}, home plant {u.plant}{dept}"

    @staticmethod
    def _scope(intent) -> str:
        parts = {
            "products": intent.products,
            "markets": intent.markets,
            "regions": intent.regions,
            "sites": intent.sites,
        }
        text = "; ".join(f"{k}: {', '.join(v)}" for k, v in parts.items() if v) or "whole portfolio"
        extra = [f"audience: {intent.audience}" if intent.audience else "", f"decision: {intent.decision_supported}"
                 if intent.decision_supported else "", f"cadence: {intent.cadence}" if intent.cadence else ""]
        return "; ".join([text, *[e for e in extra if e]])

    @staticmethod
    def _line(o: Option, in_template: bool) -> str:
        v = o.visual
        extra = ""
        if not o.feasible:
            extra = " | GAP: governed KPI without data, shown as a labelled gap"
        elif v.comparison:
            extra = f" | vs {v.comparison}"
        if v.threshold is not None:
            extra += " | lists only the rows past a governed threshold"
        return f"- {o.id} | {v.type} | {v.title}{extra}{' | default' if in_template else ''}"
