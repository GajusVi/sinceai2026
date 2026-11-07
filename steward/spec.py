"""C4 + C5 (v2): DashboardSpec, the build-ready output of a verdict. BUILD_PLAN section 3. All v2 fields are defaulted.

NIGHT draft by Gajus (Sat 7 Nov); back to Martynas at 08:00.
"""
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
    unit: str = ""  # EUR | % | weeks | units | index
    source: str = ""  # "fact_pmm.net_sales_m_eur_syn" or "derived"
    aggregation: str = "sum"  # sum | avg | ratio | derived
    definition_status: str = "canonical"
    feasible: bool = True  # False = governed KPI without source data: rendered as a labelled gap, never as a number
    gap_reason: str = ""  # "KPI-034 is governed but no governed model holds its source data"


class Visual(BaseModel):
    type: str  # card | line | bar | table | matrix
    title: str
    measures: list[str] = Field(default_factory=list)  # Measure.name
    dimension: str | None = None
    purpose: str = ""  # the decision it supports, one line
    comparison: str | None = None  # what it is shown against: "forecast" | "prior_month" | a Measure.name
    threshold: float | None = None  # for exception tables and colouring
    step: int = 0  # reading order on the page, 1 = the answer; 0 = not set (layout.py, Margiris)
    question: str = ""  # the question this visual answers, in plain words; becomes its title in the .PBIP


class Page(BaseModel):
    name: str
    visuals: list[Visual] = Field(default_factory=list)
    purpose: str = ""


class SpecChange(BaseModel):
    """One element the new version adds or alters, with the record ids that justify it (RULE-008)."""

    # add_measure | add_breakdown | swap_variant | merge_from | assign_owner | migrate_platform | remove_visual
    kind: str
    detail: str
    record_ids: list[str] = Field(default_factory=list)


class LintResult(BaseModel):
    rule_id: str  # RULE-001..008 | FOCUS | DATA
    status: str  # pass | warn | block
    message: str
    record_ids: list[str] = Field(default_factory=list)


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
    # --- v2 (C5) ---
    verdict: str = ""
    change_type: str = "create"  # reuse | extend | consolidate | create | migrate | rescue
    base_asset_ids: list[str] = Field(default_factory=list)
    version: int = 1
    changes: list[SpecChange] = Field(default_factory=list)
    audience: str = ""
    decision_supported: str = ""
    cadence: str = ""
    platform: str = "Power BI"
    lint: list[LintResult] = Field(default_factory=list)
    data_label: str = "Synthetic data from the Bayer SinceAI 2026 data pack, not Bayer performance"
    # layout_source llm|template, model, prompt file, spec_hash
    provenance: dict[str, str] = Field(default_factory=dict)
