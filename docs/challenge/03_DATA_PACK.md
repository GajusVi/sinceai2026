# 03 Data pack: Bayer_Pharmaceuticals_SinceAI_2026_FINAL_Builder_Data_Pack.xlsx (v2.0, 8 Oct 2026)

All synthetic. Product names are real public Bayer brands, values are not. No ground-truth labels, no eval answers:
**we must build our own labelled hold-out.** No patient/HCP data.

## The intended MVP (START_HERE, verbatim intent)
Business user asks a question -> AI identifies intent -> finds governed KPIs + semantic models + existing reports
-> checks usage, ownership, lineage, governance -> recommends **reuse / consolidation / migration / retirement / new build with evidence**.
Design rule: every recommendation must cite the metadata, usage, KPI, lineage or governance evidence behind it.

Suggested 6-step agent path from START_HERE:
1. Business_Requests -> parse question -> structured intent
2. KPI_Catalog -> resolve metric definitions -> governed metric set
3. Analytics_Assets + Asset_Usage -> find existing analytics (similarity + adoption + freshness) -> reuse/consolidate candidates
4. Semantic_Models + Lineage_Edges -> trace dependencies -> impact & lineage explanation
5. Governance_Signals + Data_Quality -> trust & ownership -> risk/repair actions
6. Migration_Backlog -> Tableau->Power BI -> migrate/retire/consolidate

## Sheets and keys
| Sheet | Rows | Key / joins | Notes |
| --- | --- | --- | --- |
| Products | 7 | product_id (P-NUB...) | Nubeqa, Hyrnuo (Onc); Kerendia, Xarelto, Beyonttra (CV); Eylea (Ophth); Lynkuet (WH) |
| Markets | 14 | market_id (DE, US...) | 4 regions: EMEA, North America, Asia Pacific, Latin America |
| Owners | 60 | owner_id | 13 inactive |
| Workspaces | 16 | workspace_id | WS-014 Legacy Tableau, WS-015 Sandbox, WS-016 Migration Factory, WS-008 Certified |
| KPI_Catalog | 56 | kpi_id, canonical_metric, owner_id | 18 canonical metrics, each with 1-3 variants |
| Semantic_Models | 75 | model_id, workspace_id, owner_id | 58 PBI, 17 Tableau; ai_readiness, ai_issue_pattern, refresh_status |
| Analytics_Assets | 360 | asset_id, model_id, workspace_id, owner_id | 266 PBI / 94 Tableau; Report/Workbook/App/Dashboard |
| Asset_KPI_Map | 1454 | asset_id, kpi_id | 2-6 KPIs per asset, primary/secondary |
| Asset_Usage | 3600 | asset_id x month | Jan-Oct 2026: views, unique_users, exports, subscriptions, avg_load_ms, query_errors |
| Lineage_Edges | 438 | source_id -> target_id | 360 MODEL_TO_ASSET, 56 ASSET_TO_ASSET (embedded/derived), 22 MODEL_TO_MODEL (shared upstream) |
| Governance_Signals | 410 | asset_id | 288 open / 122 acknowledged |
| Data_Quality | 147 | sheet + record_id | 126 on models, 21 on assets (owner_id) |
| Migration_Backlog | 94 | source_asset_id, candidate_target_model_id | = all 94 Tableau assets |
| Business_Requests | 150 | request_id | **primary AI input** |
| Governance_Rules | 8 | RULE-001..008 | see below |
| Product_Market_Monthly | 980 | product x market x month | 98 combos x 10 months; sales, forecast, units, access, OTIF, inventory |
| Launch_Milestones | 35 | product x market | |
| Market_Access | 98 | product x market | listed / pending / partial / not_launched |
| Supply_Operations | 98 | product x market | risk green/amber/red |
| Public_References, Data_Dictionary, Package_Overview, Change_Log | | | context |

## Governance rules (use these IDs in the UI as citations)
- RULE-001 Reuse before build (high)
- RULE-002 Canonical KPI first (high)
- RULE-003 Owner required (high)
- RULE-004 Lineage required: show upstream models + downstream impact (high)
- RULE-005 High reach requires trust: certified/promoted or reviewed (medium)
- RULE-006 Do not migrate waste: rationalise Tableau before migrating, no 1:1 recreation of duplicate low-use content (high)
- RULE-007 AI-ready semantics: business names, explicit measures, clear dates (medium)
- RULE-008 Explain every lifecycle action with evidence (high)

## Business_Requests: only 10 templates
| n | Template |
| --- | --- |
| 22 | Please create a Power BI replacement for our legacy Tableau <P> commercial workbook. |
| 20 | Can we have a new finance dashboard for net sales, gross-to-net and budget variance by product? |
| 17 | Can we build a launch dashboard for <P> with market access, first sales and adoption indicators? |
| 16 | I need a dashboard comparing product performance across oncology brands and markets. |
| 16 | Please build a new report for market access coverage and reimbursement status by product. |
| 14 | We need one executive view combining net sales, forecast accuracy and inventory coverage for Bayer Pharma. |
| 14 | I need a new <P> management report for monthly performance in EMEA and North America. |
| 13 | Can you create a country-level <P> report for launch readiness and reimbursement progress? |
| 9 | Create a global <P> dashboard showing sales growth, forecast variance and market access by country. |
| 9 | We need a monthly supply-risk dashboard by medicine and country. |
Urgency: 78 normal / 31 high / 41 urgent. Status: 78 new / 72 triaged.
=> Intent parsing is easy to make reliable; a 30-50 row hold-out covers every template.

## TRAPS / findings from profiling (these are demo gold: "the AI caught what the metadata hides")
1. **Request metadata contradicts request text.** Of 75 requests naming a product in the text, **65 have a different
   `product_context`** (e.g. REQ-0001 context=Beyonttra/EMEA, text="global Nubeqa dashboard"). Text must win; conflict
   should trigger a grill-me clarification question. Also market_context mixes country codes and regions.
2. **Lifecycle labels don't track usage.** Median 10-month views: active 2,601, candidate_retire 2,756, legacy 2,827.
   Labels are noise; recompute from Asset_Usage.
3. **estimated_audience is uncorrelated with real usage** (r = -0.01 vs views, 0.01 vs unique users). "Claimed reach vs actual reach" gap.
4. **Usage is 3-tiered**: 153 assets < 1,000 total views (Jan-Oct), 143 at ~2.5-5k, 64 > 10k. Trends are flat
   (last-3 / first-3 month ratio 0.79-1.25 for 90%), so "declining usage" can't drive retire; absolute adoption can.
5. **349 of 360 assets use at least one non-canonical KPI** (1454 links: 494 canonical, 427 duplicate_candidate,
   326 definition_conflict, 207 local_variant). KPI resolution is the core governance problem.
6. **Duplicate KPI names with different IDs**: "Inventory Coverage Mgmt" (KPI-018, 019), "Gross-to-Net Rate Legacy" (035, 036),
   "Forecast Variance Adjusted" (043, 044), "Launch Adoption Index Adjusted" (024, 026). Name-matching alone fails.
7. **Duplicate asset names**: 316 unique names for 360 assets (e.g. 3x "Nubeqa Budget Mgmt", 3x "Xarelto Budget New").
   Name suffixes Copy / v2 / New / Final / Legacy / Mgmt = sprawl signature. 46 same-product asset pairs share >=60% of canonical metrics.
8. **Ownership gap hidden from signals**: MISSING_OWNER flags the 21 null owners, but **65 more assets belong to inactive owners**
   and carry no ownership signal. Rule engine misses them; we can catch them.
9. **16 certified assets sit on semantic models whose refresh failed** (certified but stale = trust problem).
10. **Platform/workspace mismatch**: 72 of 94 Tableau assets live in Power BI workspaces; only 22 in WS-014 Legacy Tableau.
    Asset platform and model type also mismatch freely.
11. **Migration_Backlog path vs reason is inconsistent**: e.g. RETIRE with reason "high business criticality" (AST-0005),
    HUMAN_REVIEW for low complexity. Treat backlog as a candidate to second-guess, not truth (dictionary says the same).
12. **29 assets have last_modified < created_date.** Data quality flag.
13. **Governance_Signals are deterministic and reproducible** (good: our Python can re-derive them):
    HIGH_REACH_UNENDORSED = endorsement none AND estimated_audience >= ~800 (flagged min 814, unflagged max 775);
    SELF_SERVICE_HIGH_REACH = self_service AND audience >= ~1000 (flagged min 1024, unflagged max 960);
    MIGRATION_CANDIDATE = every Tableau asset (94); LIFECYCLE_REVIEW = every candidate_retire (86); MISSING_OWNER = null owner (21).
    97 assets have no signal at all.
14. **Product_Market_Monthly**: 110 rows with zero sales and null forecast_variance; 80 of them are in markets where
    Market_Access says "listed" (inconsistent). value_type flips actual_like/forecast_like month to month.
15. **Launch_Milestones**: 2 "completed" dated in the future, 6 "planned" dated in the past (vs 6 Nov 2026).
17. **Usage dated before the asset existed**: for assets created from Apr 2026, 218 of 400 usage rows are earlier than created_date.
    Count usage only from the creation month; report the rest as a data-quality finding.
16. Semantic models: ai_readiness good 30 / partial 24 / poor 21; issues poor_names 17, ambiguous_dates 16, implicit_measures 15;
    refresh healthy 42 / warning 19 / failed 14. 1 model has no assets. 1-12 assets per model (median 5).

## Profiling numbers I'd quote in the pitch (all synthetic, say so)
- 360 assets, 94 still on Tableau, 153 with < 1,000 views in 10 months.
- 18 canonical metrics fragmented into 56 KPI definitions; 97% of assets touch a non-canonical one.
- 86 assets with no accountable active owner (21 null + 65 inactive).
