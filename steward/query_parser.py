from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Protocol

from .catalog import Catalog
from .config import AMBIGUOUS_PHRASES, STOPWORDS
from .linking import GLOBAL_SCOPE, TermMatch, apply_global_scope, asks_global, find_terms, split_terms
from .llm import LLMClient
from .models import ParsedQuestion
from .prompts import render_prompt

logger = logging.getLogger(__name__)

# Russian ordinals, so "третий квартал" also parses as Q3.
_ORDINAL_QUARTERS = {"перв": 1, "втор": 2, "трет": 3, "четв": 4}


class QuestionParser(Protocol):
    def parse(self, text: str) -> ParsedQuestion: ...


class RuleBasedParser:
    """Dictionary matching. Works offline and is the fallback for the LLM parser."""

    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    def parse(self, text: str) -> ParsedQuestion:
        metrics: list[str] = []
        dimensions: list[str] = []
        filters: dict[str, str] = {}

        terms, superseded = split_terms(text, self.catalog)
        values: dict[str, list[str]] = {}
        for term in terms:
            if term.kind == "metric" and term.id not in metrics:
                metrics.append(term.id)
            elif term.kind == "dimension" and term.id not in dimensions:
                dimensions.append(term.id)
            elif term.kind == "value" and term.dimension:
                values.setdefault(term.dimension, [])
                if term.id not in values[term.dimension]:
                    values[term.dimension].append(term.id)
        apply_values(values, filters, dimensions)

        period = parse_period(text)
        if period and "quarter" not in dimensions:
            dimensions.append("quarter")

        unmapped = unmapped_terms(text, terms + superseded)
        apply_global_scope(filters, text, self.catalog)
        return finalize(
            ParsedQuestion(
                text=text, metrics=metrics, dimensions=dimensions, filters=filters, period=period, unmapped_terms=unmapped
            )
        )


class LLMParser:
    def __init__(self, catalog: Catalog, llm: LLMClient, prompts_dir: Path):
        self.catalog = catalog
        self.llm = llm
        self.prompts_dir = prompts_dir
        self.fallback = RuleBasedParser(catalog)

    def parse(self, text: str) -> ParsedQuestion:
        try:
            raw = self.llm.generate_json(
                render_prompt(self.prompts_dir, "query_parser", dictionary=self._dictionary(), question=text)
            )
            parsed = self._validate(text, raw)
        except Exception:
            logger.warning("llm_parse_failed", exc_info=True)
            return self.fallback.parse(text)
        if not parsed.metrics:
            return self.fallback.parse(text)
        return parsed

    def _validate(self, text: str, raw: dict) -> ParsedQuestion:
        """Drops every id the dictionary does not know, so the model cannot invent metrics."""
        metrics = [m for m in raw.get("metrics", []) if m in self.catalog.metrics]
        dimensions = [d for d in raw.get("dimensions", []) if d in self.catalog.dimensions]
        filters = {}
        for dimension_id, value_id in (raw.get("filters") or {}).items():
            dimension = self.catalog.dimensions.get(dimension_id)
            if dimension and any(v.id == value_id for v in dimension.values):
                filters[dimension_id] = value_id
        period = raw.get("period") or parse_period(text)
        if period and "quarter" not in dimensions:
            dimensions.append("quarter")
        # The model returns one value per dimension; the rules catch a second one ("Xarelto vs Eylea").
        apply_values(multi_values(text, self.catalog), filters, dimensions, only_multi=True)
        apply_global_scope(filters, text, self.catalog)
        # The model may flag terms the dictionary lacks; the rule check catches words it silently skipped.
        unmapped = [str(t).strip() for t in raw.get("unmapped") or [] if str(t).strip()]
        kept, superseded = split_terms(text, self.catalog)
        for term in unmapped_terms(text, kept + superseded):
            if not any(term.lower() in u.lower() for u in unmapped):
                unmapped.append(term)
        return finalize(
            ParsedQuestion(
                text=text,
                metrics=metrics,
                dimensions=dimensions,
                filters=filters,
                period=period,
                parser="llm",
                unmapped_terms=unmapped,
            )
        )

    def _dictionary(self) -> str:
        lines = ["Metrics:"]
        lines += [f"- {m.id}: {m.name}; synonyms: {', '.join(m.synonyms)}" for m in self.catalog.metrics.values()]
        lines.append("Dimensions:")
        for d in self.catalog.dimensions.values():
            values = ", ".join(f"{v.id} ({v.label})" for v in d.values) or "no fixed values"
            lines.append(f"- {d.id}: {d.name}; values: {values}")
        return "\n".join(lines)


_WORD = re.compile(r"\w+", re.UNICODE)


def unmapped_terms(text: str, terms: list[TermMatch]) -> list[str]:
    """Content words that no dictionary term, period or stopword covers. They must never be dropped silently."""
    lowered = text.lower()
    covered = [(t.start, t.end) for t in terms]
    out: list[str] = []
    for phrase in AMBIGUOUS_PHRASES:  # reported as one phrase, e.g. "first sales", not as loose words
        for match in re.finditer(rf"(?<!\w){re.escape(phrase)}", lowered):
            covered.append(match.span())
            if text[match.start() : match.end()] not in out:
                out.append(text[match.start() : match.end()])
    for word in _WORD.finditer(lowered):
        token = word.group(0)
        if any(start < word.end() and word.start() < end for start, end in covered):
            continue
        if token.isdigit() or re.fullmatch(r"q[1-4]", token) or len(token) < 2:
            continue
        if token in STOPWORDS or token.rstrip("s") in STOPWORDS:
            continue
        if text[word.start() : word.end()] not in out:
            out.append(text[word.start() : word.end()])
    return out


def multi_values(text: str, catalog: Catalog) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for term in find_terms(text, catalog):
        if term.kind == "value" and term.dimension and term.id not in out.setdefault(term.dimension, []):
            out[term.dimension].append(term.id)
    return out


def apply_values(
    values: dict[str, list[str]], filters: dict[str, str], dimensions: list[str], only_multi: bool = False
) -> None:
    """One named value is a filter. Several ("Xarelto vs Eylea", "Brazil and Japan") are a breakdown, as in
    Intent.to_parsed_question: the first is never kept silently while the others vanish."""
    for dimension, ids in values.items():
        if len(ids) > 1:
            filters.pop(dimension, None)
            if dimension not in dimensions:
                dimensions.append(dimension)
        elif ids and not only_multi:
            filters.setdefault(dimension, ids[0])


def finalize(question: ParsedQuestion) -> ParsedQuestion:
    """A dimension that is already filtered ("in LATAM") is not also a breakdown. A question that says "global" but
    also names a place contradicts itself: ask which one is meant."""
    question.dimensions = [d for d in question.dimensions if d not in question.filters]
    named_place = question.filters.get("market", GLOBAL_SCOPE) != GLOBAL_SCOPE or "region" in question.filters
    if asks_global(question.text) and named_place:
        place = question.filters.get("market") or question.filters.get("region")
        message = f'The question says "global" but also names a place ({place}): which one is meant?'
        if message not in question.conflicts:
            question.conflicts.append(message)
    return question


def parse_period(text: str) -> str | None:
    lowered = text.lower()
    year_match = re.search(r"\b(20\d{2})\b", lowered)
    year = f"{year_match.group(1)}-" if year_match else ""

    quarter = None
    if match := re.search(r"\bq([1-4])\b", lowered):
        quarter = int(match.group(1))
    elif match := re.search(r"\b([1-4])\s*-?\s*(?:й|ый|ой)?\s*квартал", lowered):
        quarter = int(match.group(1))
    elif match := re.search(r"\b(перв|втор|трет|четв)\w*\s+квартал", lowered):
        quarter = _ORDINAL_QUARTERS[match.group(1)]

    return f"{year}Q{quarter}" if quarter else None


def get_parser(catalog: Catalog, llm: LLMClient | None, prompts_dir: Path) -> QuestionParser:
    return LLMParser(catalog, llm, prompts_dir) if llm else RuleBasedParser(catalog)
