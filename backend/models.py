"""Typed objects for the decision layer. Rename Item to the company's noun on Friday
(Ticket, Asset, Document, Supplier...), keep the shape."""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


class Item(BaseModel):
    id: str
    text: str
    meta: dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    """What the model returns for one item. Keep it small: every field must show up in the UI."""

    label: str = Field(description="one of the allowed labels")
    priority: int = Field(ge=1, le=5, description="5 = act now, 1 = can wait")
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(description="one sentence a non-expert understands")
    evidence: list[str] = Field(default_factory=list, description="short verbatim quotes from the input")
    suggested_action: str = Field(description="the single next step for the user")


class ScoredItem(BaseModel):
    item: Item
    decision: Decision
    source: Literal["llm", "cache", "rules"]
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Review(BaseModel):
    item_id: str
    verdict: Literal["approve", "reject"]
    note: str = ""
    reviewer: str = "analyst"
