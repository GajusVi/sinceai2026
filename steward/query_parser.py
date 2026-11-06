from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Protocol

from .catalog import Catalog
from .config import STOPWORDS
from .linking import TermMatch, find_terms
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

        terms = find_terms(text, self.catalog)
        for term in terms:
            if term.kind == "metric" and term.id not in metrics:
                metrics.append(term.id)
            elif term.kind == "dimension" and term.id not in dimensions:
                dimensions.append(term.id)
            elif term.kind == "value" and term.dimension:
                filters.setdefault(term.dimension, term.id)

        period = parse_period(text)
        if period and "quarter" not in dimensions:
            dimensions.append("quarter")

        unmapped = unmapped_terms(text, terms)
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
        # The model may flag terms the dictionary lacks; the rule check catches words it silently skipped.
        unmapped = [str(t).strip() for t in raw.get("unmapped") or [] if str(t).strip()]
        for term in unmapped_terms(text, find_terms(text, self.catalog)):
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


def finalize(question: ParsedQuestion) -> ParsedQuestion:
    """A dimension that is already filtered ("in LATAM") is not also a breakdown."""
    question.dimensions = [d for d in question.dimensions if d not in question.filters]
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
