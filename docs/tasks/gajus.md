# Gajus: NIGHT SHIFT (Sat 03:30 → 08:30), then Saturday

Tell your Claude Code: "Do the NIGHT SHIFT in docs/tasks/gajus.md. Read CLAUDE.md and docs/BUILD_PLAN.md sections 0-6 first."
Goal: a rough but complete W0→W9 draft running on the data pack by 08:30, so Panu sees a real dashboard at 09:00 (BUILD_PLAN 6.1).
Track A (you) alone gives the end-to-end draft. Margiris (Track B) adds lint, CONSOLIDATE/NOT_FEASIBLE and the TMDL export.
**Rough is fine, broken is not:** plain layout, template text, one test per module, `make test` green before every push.
Tonight you are the NIGHT owner of steward/spec.py, steward/semantic.py, catalog/bayer/measures.json, steward/render.py and
frontend/steward_app.py (OWNERS). Owners take them back at 08:00, so keep the code plain and commented where a choice was made.
Push after each N-task and post `tools/coord.py say all "..." --kind done` (commit id, how to call it, what is rough).

## N1 (03:30-04:00) spec contract v2 + fixture
`steward/spec.py`: add exactly the fields of BUILD_PLAN section 3 (C5). All defaulted, nothing renamed, tests/bi_steward/test_spec.py stays green.
Fixture `tests/bi_steward/fixtures/spec_req0001.json`: run `make bayer` logic in Python (`Steward.ask` on the REQ-0001 text without
metadata) to get the best asset id; write an EXTEND spec on it: 1 page "What needs attention", 3 KPI cards (KPI-001 Net Sales,
KPI-004 Net Sales Growth, KPI-042 Forecast Variance), 1 line (net sales vs forecast by month), 1 bar (net sales by market),
1 exceptions table (|forecast variance %| > 10), one SpecChange per added element with record ids. Test: it validates.
**Push by 04:00 and say all: Margiris starts lint on it.**

## N2 (04:00-05:00) the semantic layer
`catalog/bayer/measures.json`: 18 entries (kpi_id, measure name, unit, format, source, aggregation, DAX expression, feasible, gap_reason),
bindings exactly as BUILD_PLAN section 4 (12 bound, 6 gaps). `steward/semantic.py`:
- `load_frames()` cached: fact_pmm (Product_Market_Monthly), fact_supply, fact_access, fact_launch, fact_usage (Asset_Usage),
  dim_product, dim_market (with region from catalog/bayer/regions.json), dim_month. Read the xlsx with pandas + openpyxl (installed).
- `star_schema()` → entities, columns, relationships (facts many_to_one to the dims on product_id / market_id / month).
- `measure(kpi_id) -> Measure` and `compute(measure, frames, filters, by=None) -> DataFrame` (month or dimension series; derived
  measures: growth = vs prior month, bias = (sales − forecast) / forecast, forecast variance EUR = sales − forecast).
- `feasibility(intent) -> Feasibility(buildable, gaps, scope_ok, nearest)`; trap 14: zero-sales rows with null variance excluded from
  averages, counted as a DQ note.
Tests: REQ-0001 metrics → 3 buildable; net sales + gross-to-net + budget variance → 1 buildable + gaps KPI-034, KPI-039. Push, say all.

## N3 (05:00-06:15) spec builder + pipeline
`steward/specbuild.py`: `spec_from_asset(asset, catalog)` (its kpi_ids → canonical measures; variants become swap_variant changes),
`build_spec(decision, intent, catalog, feasibility) -> DashboardSpec | None` for **REUSE, EXTEND, CREATE** only tonight
(None for CLARIFY / NOT_FEASIBLE; CONSOLIDATE falls back to EXTEND on the keeper until Saturday). CREATE picks the best governed model:
Power BI, certified > promoted, refresh healthy, product scope match (else All Pharma). Template layout per BUILD_PLAN 5.1:
≤ 4 cards, 1 trend with comparison, 1 breakdown by the intent's dimension (market if several markets, product if several products),
1 exceptions table; infeasible measures stay as gap measures. Owner default = source model owner.
`steward/pipeline.py`: `Steward.build(decision, intent)` = feasibility → build_spec → `lint` if `steward.lint` imports (Margiris's N5), else empty.
`StewardResult` gets `spec`. Test: REUSE, EXTEND and CREATE specs on 3 real questions. Push, say all.

## N4 (06:15-08:00) render + the dashboard on screen
`steward/render.py`: `render(spec, frames, filters) -> RenderedDashboard(cards, figures, tables, gaps, footer)`, Plotly only.
Cards: value + comparison delta; line: measure by month with comparison; bar: by dimension; table: exceptions past threshold, worst first;
gap card for `feasible=False` (grey, gap_reason, **never a number**); footer: KPI ids + status, model id + endorsement + refresh, owner,
version, data_label. `frontend/steward_app.py`, under the decision in the Ask flow: the dashboard (2-column grid), product / market /
month filters, the lint panel (pass / warn / block from spec.lint; block disables approve), approve writes spec_hash + lint summary
into the journal entry (steward/governance.py, shared: small change), "Download spec JSON" button. Keep Donatas's existing tabs intact.
Done when: `make bayer`, REQ-0001 text → EXTEND → dashboard renders → approve → journal shows the spec hash. `make test` green.

## 08:15 handover
`tools/coord.py status --now ... --done ... --next ...`; 3 lines in NOTES.md (done / rough / missing). Then 08:30 S2, 09:00 Panu Q&A
with the running draft: show it, ask Q2 (BUILD_PLAN 6.2), write his feedback into NOTES.md. That list drives S3 at 12:00.

---
Tell your Claude Code: "Do docs/tasks/gajus.md. Read CLAUDE.md and docs/BUILD_PLAN.md sections 0-6 first."
## Saturday (after the night shift): feedback, hardening, design
- **08:30 S2, 09:00 Panu Q&A with the running draft** (with Donatas): show REQ-0001 end to end, ask the 5 questions in
  docs/challenge/05_SYNTHESIS.md + new Q2 (BUILD_PLAN 6.2). Write his feedback into NOTES.md as a numbered list by 12:00 (drives S3).
- **G9 (P0)** specbuild: CONSOLIDATE (union of canonical KPIs, keeper + retire list with lineage impact), MIGRATE (Tableau → Power BI,
  rationalised, RULE-006), RESCUE (orphan + successor) on top of the night's REUSE/EXTEND/CREATE. Done when: 6 cases in tests, each passes lint or fails for the right reason.
- **G10 (P1)** prompts/to_spec.yaml + validator: LLM picks headline measure, comparison and exception threshold from a fixed menu and
  writes name, titles, rationale; code rejects anything outside the menu and any digit; template fallback; provenance.layout_source.
- **G11 (P1)** headline numbers from code: all 150 Business_Requests through the pipeline (rules mode): % without a new dashboard,
  NOT_FEASIBLE gaps by KPI, flags. Script committed; numbers never typed by hand.
- **G6 (P0) README** (brief section 07) + **G7 pitch**: data assumptions, AI approach (LLM steps vs code), governance controls (lint table),
  enterprise BI integration (PBIP in git, Fabric deployment APIs, scanner APIs), limitations (synthetic data, PBIP status as verified).
  Swap the herbicide example in the README diagrams for REQ-0001 (Crop Science is out of scope).
