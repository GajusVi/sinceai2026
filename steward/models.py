from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class MetricDefinition(BaseModel):
    id: str
    name: str
    formula: str
    owner: str
    domain: str
    synonyms: list[str] = Field(default_factory=list)


class DimensionValue(BaseModel):
    id: str
    label: str
    synonyms: list[str] = Field(default_factory=list)


class DimensionDefinition(BaseModel):
    id: str
    name: str
    synonyms: list[str] = Field(default_factory=list)
    values: list[DimensionValue] = Field(default_factory=list)


class ArtifactMetric(BaseModel):
    label: str
    formula: str


class ArtifactStatus(str, Enum):
    ACTIVE = "active"
    DRAFT = "draft"
    SUPERSEDED = "superseded"


class Artifact(BaseModel):
    id: str
    title: str
    type: str
    description: str
    domain: str
    metrics: list[ArtifactMetric]
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, str] = Field(default_factory=dict)
    owner: str = ""
    owner_active: bool = False
    certified: bool = False
    last_refreshed: date
    views_30d: int = 0
    family_id: str
    version: int = 1
    previous_id: str | None = None
    status: ArtifactStatus = ArtifactStatus.ACTIVE
    source_tables: list[str] = Field(default_factory=list)

    @property
    def has_owner(self) -> bool:
        return bool(self.owner) and self.owner_active


class ParsedQuestion(BaseModel):
    text: str
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, str] = Field(default_factory=dict)
    period: str | None = None
    parser: str = "rules"


class Verdict(str, Enum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    CREATE = "CREATE"
    CLARIFY = "CLARIFY"


class GapKind(str, Enum):
    METRIC = "metric"
    DIMENSION = "dimension"
    FILTER = "filter"
    SCOPE = "scope"
    TRUST = "trust"


class Gap(BaseModel):
    kind: GapKind
    key: str
    value: str | None = None


class MetricConflict(BaseModel):
    artifact_id: str
    artifact_title: str
    label: str
    metric_id: str
    artifact_formula: str
    official_formula: str
    actual_metric_id: str | None = None


class Candidate(BaseModel):
    artifact: Artifact
    search_score: float
    coverage: float
    trust: float
    covered: list[str]
    gaps: list[Gap]
    compatible: bool
    score: float


class Decision(BaseModel):
    verdict: Verdict
    best: Candidate | None = None
    alternatives: list[Candidate] = Field(default_factory=list)
    conflicts: list[MetricConflict] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class StewardResult(BaseModel):
    question: ParsedQuestion
    decision: Decision
    explanation: str
    as_of: date


class JournalAction(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"


class JournalEntry(BaseModel):
    timestamp: datetime
    actor: str
    question: str
    verdict: Verdict
    action: JournalAction
    artifact_id: str | None = None
    created_artifact_id: str | None = None
    coverage: float | None = None
    trust: float | None = None
    reason: str = ""
