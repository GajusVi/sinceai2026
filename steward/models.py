from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field

from .spec import DashboardSpec


class MetricVariant(BaseModel):
    kpi_id: str
    kpi_name: str = ""
    definition_status: str = ""
    approval_status: str = ""
    owner_id: str = ""


class MetricDefinition(BaseModel):
    id: str
    name: str
    formula: str
    owner: str
    domain: str
    synonyms: list[str] = Field(default_factory=list)
    kpi_id: str = ""
    unit: str = ""
    variants: list[MetricVariant] = Field(default_factory=list)


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


class UsageMonth(BaseModel):
    month: date
    views: int = 0
    unique_users: int = 0
    exports: int = 0
    subscriptions: int = 0
    query_errors: int = 0


class Evidence(BaseModel):
    """One cited reason behind a decision (RULE-008)."""

    claim: str  # "Owner OWN-018 is inactive"
    rule_id: str | None = None  # "RULE-003"
    record_ids: list[str] = Field(default_factory=list)  # ["AST-0091", "OWN-018"]
    value: str | None = None  # "309 users/month"
    severity: str = "info"  # info | warning | blocker


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
    # Data-pack fields (all defaulted so the sample catalog keeps loading)
    platform: str = ""
    workspace_id: str = ""
    model_id: str = ""
    product_scope: str = ""  # product name or "All Pharma"
    market_scope: str = ""  # market_id or "Global"
    kpi_ids: list[str] = Field(default_factory=list)
    endorsement: str = "none"  # certified | promoted | none
    lifecycle_claimed: str = ""  # data-pack label, NOT trusted
    created_date: date | None = None
    owner_id: str = ""
    owner_role: str = ""
    owner_scope: str = ""
    owner_status: str = ""  # active | inactive | "" = missing
    successor_candidates: list[str] = Field(default_factory=list)
    usage: list[UsageMonth] = Field(default_factory=list)
    refresh_status: str = ""  # semantic model: healthy | warning | failed
    model_endorsement: str = ""
    signals: list[str] = Field(default_factory=list)  # "CODE:severity:status"
    data_quality: list[str] = Field(default_factory=list)  # DQ ids
    upstream_ids: list[str] = Field(default_factory=list)
    downstream_ids: list[str] = Field(default_factory=list)

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
    unmapped_terms: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)


class Verdict(str, Enum):
    REUSE = "REUSE"
    EXTEND = "EXTEND"
    CREATE = "CREATE"
    CLARIFY = "CLARIFY"
    CONSOLIDATE = "CONSOLIDATE"
    NOT_FEASIBLE = "NOT_FEASIBLE"


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
    evidence: list[Evidence] = Field(default_factory=list)
    # REASSIGN_OWNER, RETIRE, MIGRATE, FIX_REFRESH, CONSOLIDATE
    flags: list[str] = Field(default_factory=list)


class StewardResult(BaseModel):
    question: ParsedQuestion
    decision: Decision
    explanation: str
    as_of: date
    spec: DashboardSpec | None = None  # set by Steward.build(): the dashboard this decision implies (W5-W6)


class JournalAction(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    PROPOSED = "proposed"  # recorded only, catalog unchanged (e.g. propose successor, retire candidate)


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
