"""Intent: the contract between the interview (LLM) and the evidence engine (code). BUILD_PLAN section 2.6-2.7."""

from __future__ import annotations

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
    metric_ids: list[str] = Field(default_factory=list)  # canonical metric ids from catalog/bayer/metrics.json
    unmapped_terms: list[str] = Field(
        default_factory=list
    )  # words we could not map: they block REUSE (no silent drops)
    grain: Literal["month", "quarter"] = "month"
    comparison: Literal["target", "forecast", "prior"] | None = None
    audience: str = ""
    conflicts: list[str] = Field(default_factory=list)  # e.g. "text says Nubeqa, request metadata says Beyonttra"
    confidence: dict[str, float] = Field(default_factory=dict)  # field name -> 0..1
    mode: Mode = "novice"
    text: str = ""  # the original question, for display and for search

    def missing(self) -> list[str]:
        """Required fields that are empty or below CONFIDENCE_MIN. Order = the order the interview should ask in."""
        required = {
            "products": bool(self.products),
            "markets": bool(self.markets or self.regions),
            "metric_ids": bool(self.metric_ids),
            "decision_supported": bool(self.decision_supported),
        }
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

    def to_parsed_question(self) -> ParsedQuestion:
        """Adapter so the current engine runs on an Intent: one value -> filter, several -> breakdown dimension."""
        filters: dict[str, str] = {}
        dimensions: list[str] = []
        for dim, values in (("product", self.products), ("market", self.markets), ("region", self.regions)):
            if len(values) == 1:
                filters[dim] = values[0]
            elif len(values) > 1:
                dimensions.append(dim)
        if self.grain not in dimensions:
            dimensions.append(self.grain)

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
