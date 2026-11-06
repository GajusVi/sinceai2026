# Martynas: tonight 00:05 → 01:00 (contracts + dictionaries)

Tell your Claude Code: "Do docs/tasks/martynas.md. Read CLAUDE.md and docs/BUILD_PLAN.md section 2 first."
Order matters: **T1 first and push it by 00:30**, Gajus's loader and Margiris's logic import these fields.
Rule for every new field: **give it a default**, so the old sample catalog and the 28 tests keep passing.

## T1 (C1 + C3 fields) `steward/models.py`, push by 00:30
Add, keep every existing field:
```python
class UsageMonth(BaseModel):
    month: date
    views: int = 0
    unique_users: int = 0
    exports: int = 0
    subscriptions: int = 0
    query_errors: int = 0

class Evidence(BaseModel):          # C3: one cited reason behind a decision (RULE-008)
    claim: str                      # "Owner OWN-018 is inactive"
    rule_id: str | None = None      # "RULE-003"
    record_ids: list[str] = Field(default_factory=list)   # ["AST-0091", "OWN-018"]
    value: str | None = None        # "309 users/month"
    severity: str = "info"          # info | warning | blocker
```
`Artifact` gets (all with defaults): `platform: str = ""`, `workspace_id: str = ""`, `model_id: str = ""`,
`product_scope: str = ""` (product name or "All Pharma"), `market_scope: str = ""` (market_id or "Global"),
`kpi_ids: list[str]`, `endorsement: str = "none"` (certified|promoted|none), `lifecycle_claimed: str = ""` (data-pack label, NOT trusted),
`created_date: date | None = None`, `owner_id: str = ""`, `owner_role: str = ""`, `owner_scope: str = ""`,
`owner_status: str = ""` (active|inactive|"" = missing), `successor_candidates: list[str]`, `usage: list[UsageMonth]`,
`refresh_status: str = ""` (semantic model: healthy|warning|failed), `model_endorsement: str = ""`,
`signals: list[str]` ("CODE:severity:status"), `data_quality: list[str]` (DQ ids), `upstream_ids: list[str]`, `downstream_ids: list[str]`.
`Verdict` gets `CONSOLIDATE` and `NOT_FEASIBLE`. `Decision` gets `evidence: list[Evidence]` and `flags: list[str]`
(REASSIGN_OWNER, RETIRE, MIGRATE, FIX_REFRESH, CONSOLIDATE). `ParsedQuestion` gets `unmapped_terms: list[str]` and `conflicts: list[str]`.
Done when: `make test` green, pushed, one line in NOTES.md.

## T2 (C4) new file `steward/spec.py`
Pydantic: `Relationship(from_entity, to_entity, cardinality="many_to_one", key="")`,
`Measure(name, kpi_id, expression="", format="")`, `Visual(type, title, measures: list[str], dimension: str | None)`,
`Page(name, visuals: list[Visual])`, `DashboardSpec(name, entities, columns: dict[str, list[str]], grain: dict[str, str],
relationships, measures, pages, filters: dict[str, str], kpi_ids, source_model_id, owner_id, rationale="")`.
Add `tests/bi_steward/test_spec.py` with one hand-written example (Nubeqa, Germany, Net Sales KPI-001 + Forecast Variance KPI-042, monthly).

## T3 (D2) new file `catalog/bayer/metrics.json` (do NOT touch catalog/metrics.json, the tests use it)
One entry per canonical metric (18), shaped like the existing file plus extra keys:
`{"id": "net_sales", "name": "Net Sales", "kpi_id": "KPI-001", "formula": "governed definition KPI-001 (synthetic: no formula in data pack)",
"owner": "OWN-041", "domain": "Commercial", "synonyms": [...], "variants": [{"kpi_id": "KPI-002", "kpi_name": "Net Sales Local",
"definition_status": "definition_conflict", "approval_status": "unapproved", "owner_id": "OWN-004"}, ...]}`
Generate ids/kpi/variants from the KPI_Catalog sheet with a script; then review these **draft synonyms** (lowercase, they are word-start stems):
net_sales: net sales, sales, revenue, turnover · net_sales_growth: sales growth, growth · demand_forecast_accuracy: forecast accuracy ·
demand_forecast_bias: forecast bias · units_shipped: units shipped, units, volume, shipments · inventory_coverage: inventory coverage,
inventory, stock cover, weeks of supply · on_time_in_full: otif, on-time in-full, on time in full · launch_adoption_index: launch adoption, adoption, uptake ·
market_access_coverage: market access · reimbursement_status_coverage: reimbursement · gross_to_net_rate: gross-to-net, gross to net, gtn ·
operating_contribution: operating contribution, contribution · budget_variance: budget variance, vs budget, budget ·
forecast_variance: forecast variance, vs forecast · commercial_reach_index: commercial reach · digital_engagement_index: digital engagement ·
report_adoption: report adoption, report usage · certified_asset_share: certified asset share, certification rate.
Deliberately NOT synonyms (ambiguous, must go to CLARIFY): "coverage", "forecast", "performance", "first sales", "readiness".
**Bad-name trap:** "Inventory Coverage Mgmt", "Gross-to-Net Rate Legacy", "Forecast Variance Adjusted", "Launch Adoption Index Adjusted" each exist twice with different ids: keep both ids in variants.

## T4 (D3) new files `catalog/bayer/dimensions.json` + `catalog/bayer/regions.json`
dimensions.json (same shape as catalog/dimensions.json): `product` (values P-NUB..P-HYR, label = name, synonyms = lowercase name;
dimension synonyms: by product, product, brand, medicine), `market` (14 values, label = market_name, synonyms = lowercase full names
plus "usa", "united states", "britain"; **no 2-letter codes**: the linker matches word starts, so "it" would match "items"),
`region` (EMEA, North America, Asia Pacific + "apac", Latin America + "latam"), `month` (by month, monthly), `quarter` (quarterly, by quarter).
regions.json: `{"EMEA": ["DE","FR","IT","ES","FI","SE","UK"], "North America": ["US","CA"], "Asia Pacific": ["JP","CN","AU"], "Latin America": ["BR","MX"]}`.

## 00:55 handover
Push, then 3 lines in NOTES.md under Decisions: done / half-done / next. Saturday 08:00: D5 hold-out labelling with Margiris, then D6 preview.
