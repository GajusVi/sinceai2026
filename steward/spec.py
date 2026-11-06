"""C4: DashboardSpec, the build-ready output of a CREATE/EXTEND decision."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Relationship(BaseModel):
    from_entity: str
    to_entity: str
    cardinality: str = "many_to_one"
    key: str = ""


class Measure(BaseModel):
    name: str
    kpi_id: str
    expression: str = ""
    format: str = ""


class Visual(BaseModel):
    type: str  # card | line | bar | table | matrix
    title: str
    measures: list[str] = Field(default_factory=list)  # Measure.name
    dimension: str | None = None


class Page(BaseModel):
    name: str
    visuals: list[Visual] = Field(default_factory=list)


class DashboardSpec(BaseModel):
    name: str
    entities: list[str] = Field(default_factory=list)
    columns: dict[str, list[str]] = Field(default_factory=dict)  # entity -> columns
    grain: dict[str, str] = Field(default_factory=dict)  # entity -> grain, e.g. {"fact": "month"}
    relationships: list[Relationship] = Field(default_factory=list)
    measures: list[Measure] = Field(default_factory=list)
    pages: list[Page] = Field(default_factory=list)
    filters: dict[str, str] = Field(default_factory=dict)
    kpi_ids: list[str] = Field(default_factory=list)
    source_model_id: str = ""
    owner_id: str = ""
    rationale: str = ""
