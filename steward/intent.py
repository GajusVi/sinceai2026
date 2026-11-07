"""Intent: the contract between the interview (LLM) and the evidence engine (code). BUILD_PLAN section 2.6-2.7."""

from __future__ import annotations

import re

from typing import Literal

from pydantic import BaseModel, Field

from .models import ParsedQuestion

CONFIDENCE_MIN = 0.7  # interview stop rule (BUILD_PLAN 2.7)
MAX_QUESTIONS = 5

Mode = Literal["novice", "expert", "rescue"]


class Intent(BaseModel):
    role: str = ""
    decision_supported: str = ""
    cadence: str = ""
    products: list[str] = Field(default_factory=list)  # product names as in the data pack ("Nubeqa")
    markets: list[str] = Field(default_factory=list)  # market ids ("DE")
    regions: list[str] = Field(default_factory=list)  # "EMEA", "North America", ...
    sites: list[str] = Field(default_factory=list)  # supply sites: "Plant-A" .. "Plant-C", "External-CMO"
    theme: str = ""  # goal theme key from prompts/interview.yaml ("plant_efficiency"); its metrics need confirming
    metric_ids: list[str] = Field(default_factory=list)  # canonical metric ids from catalog/bayer/metrics.json
    unmapped_terms: list[str] = Field(
        default_factory=list
    )  # words we could not map: they block REUSE (no silent drops)
    ignored_terms: list[str] = Field(default_factory=list)  # left over after the interview: a note, never a blocker
    grain: Literal["month", "quarter"] = "month"
    comparison: Literal["target", "forecast", "prior"] | None = None
    audience: str = ""
    conflicts: list[str] = Field(default_factory=list)  # e.g. "text says Nubeqa, request metadata says Beyonttra"
    confidence: dict[str, float] = Field(default_factory=dict)  # field name -> 0..1
    mode: Mode = "novice"
    text: str = ""  # the original question, for display and for search

    def missing(self) -> list[str]:
        """Required fields that are empty or below CONFIDENCE_MIN. Order = the order the interview should ask in.
        A named site is a full scope on its own (everything the site supplies): products and markets are not asked."""
        site_scope = bool(self.sites) and self._conf("sites") >= CONFIDENCE_MIN
        required = {
            "products": site_scope or bool(self.products),
            "markets": site_scope or bool(self.markets or self.regions),
            "metric_ids": bool(self.metric_ids),
            "decision_supported": bool(self.decision_supported),
        }
        if site_scope:
            required = {k: v for k, v in required.items() if k not in ("products", "markets")}
        return [name for name, filled in required.items() if not filled or self._conf(name) < CONFIDENCE_MIN]

    def _conf(self, name: str) -> float:
        if name == "markets":  # markets or regions: the better of the two counts
            return max(self.confidence.get("markets", 0.0), self.confidence.get("regions", 0.0))
        return self.confidence.get(name, 0.0)

    def is_complete(self) -> bool:
        """Stop rule: products, markets or regions, >= 1 metric, decision_supported, all confidence >= 0.7."""
        return not self.missing()

    def should_stop(self, questions_asked: int) -> bool:
        """Open conflicts keep the interview going (any mode); expert mode asks only on conflicts.

        MAX_QUESTIONS always stops it."""
        if questions_asked >= MAX_QUESTIONS:
            return True
        if self.conflicts:
            return False
        return self.mode == "expert" or self.is_complete()

    def to_parsed_question(self, catalog=None) -> ParsedQuestion:
        """Adapter so the current engine runs on an Intent: one value -> filter, several -> breakdown dimension.

        The Intent keeps display names ("Xarelto"); the engine and the assets use ids ("P-XAR"). With `catalog`, every
        filter value is mapped to its id here, the one boundary (audit F1: names here turned REUSE into CREATE). "All
        Pharma" is no product filter, as in the rules parser. Without a catalog (unit tests only) values pass as they are."""
        filters: dict[str, str] = {}
        dimensions: list[str] = []
        for dim, values in (("product", self.products), ("market", self.markets), ("region", self.regions)):
            if len(values) == 1:
                value = value_id(catalog, dim, values[0]) if catalog is not None else values[0]
                if not (dim == "product" and value.lower() == ALL_PHARMA.lower()):
                    filters[dim] = value
            elif len(values) > 1:
                dimensions.append(dim)
        if self.grain not in dimensions and _TIME_WORDS.search(self.text or ""):
            dimensions.append(self.grain)  # a time breakdown is required only when the user asked for one (audit F1)

        extra = {}  # fields added to ParsedQuestion by contract C3; set only if present
        if "unmapped_terms" in ParsedQuestion.model_fields:
            extra["unmapped_terms"] = list(self.unmapped_terms)
        if "conflicts" in ParsedQuestion.model_fields:
            extra["conflicts"] = list(self.conflicts)
        return ParsedQuestion(
            text=self.text,
            metrics=list(self.metric_ids),
            dimensions=dimensions,
            filters=filters,
            parser=f"intent:{self.mode}",
            **extra,
        )


_TIME_WORDS = re.compile(r"\b(month|monthly|quarter|quarterly|week|weekly|trend|over time|by period)\b", re.I)
ALL_PHARMA = "All Pharma"  # = steward.datapack.ALL_PHARMA (not imported: datapack pulls in pandas)


def value_id(catalog, dimension: str, value: str) -> str:
    """The catalog id for a dimension value given as id or label, any case ("Xarelto" -> "P-XAR", "germany" -> "DE").
    Unknown values are returned unchanged (the engine then reports them; nothing is silently dropped here)."""
    dim = getattr(catalog, "dimensions", {}).get(dimension)
    wanted = value.strip().lower()
    for v in getattr(dim, "values", []) or []:
        if wanted in (v.id.lower(), v.label.lower()):
            return v.id
    return value


def intent_from_parsed(question: ParsedQuestion, catalog) -> Intent:
    """The plain Ask flow has no interview: build an Intent from the parser output so the same dashboard path can run.
    Value ids become names (P-NUB -> Nubeqa) and "Global" stays "Global"."""
    product_id = question.filters.get("product")
    products = [catalog.dimension_value_label("product", product_id)] if product_id else []
    markets = [question.filters["market"]] if "market" in question.filters else []
    regions = [question.filters["region"]] if "region" in question.filters else []
    grain = "quarter" if "quarter" in question.dimensions else "month"
    return Intent(
        products=products, markets=markets, regions=regions, metric_ids=list(question.metrics), grain=grain,
        unmapped_terms=list(getattr(question, "unmapped_terms", [])),
        conflicts=list(getattr(question, "conflicts", [])),
        text=question.text, mode="expert",
    )
