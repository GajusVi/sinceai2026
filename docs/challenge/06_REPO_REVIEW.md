# 06 Review of Donatas's skeleton: vladafink/bi-steward (zip, read 6 Nov 21:30)

~2,900 lines Python + docs. Streamlit UI, pydantic models, 22 tests. **Ran it: `uv sync && uv run pytest` -> 22 passed.**
No charts in the repo (only mermaid diagrams in docs/architecture.md).

## Verdict
Keep it as the base. The architecture already matches our plan: reuse-before-build gate, deterministic verdict,
LLM only parses and explains (with guardrails + rules fallback), human approve/reject with reason, journal,
catalog-health screen, golden-question contract. Roughly 60-70% of the engine survives.

Two blocking problems:
1. **It runs on its own invented catalog** (18 reports: herbicides, Crop Science LATAM, Consumer Health NPS, clinical trials,
   adverse events). The data pack says Pharma only, no Crop Science/Consumer Health, clinical + pharmacovigilance out of scope.
   Must be rewired to the 360-asset data pack.
2. **Silent false positives (Donatas's own concern, reproduced).** Real request REQ-0001
   "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country"
   -> `REUSE "Global Net Revenue vs Plan", coverage 100%, trust 1.00`.
   Only "sales" was recognised; growth, forecast variance, market access, Nubeqa, by-country were dropped without a word,
   and coverage is computed over the recognised part only. The LLM validator also silently drops unknown ids.
   Fix: parser returns `unmapped_terms`; they count in the coverage denominator; parse confidence below threshold -> clarify.

## File-by-file
| File | Call | Why / what to change |
|---|---|---|
| steward/search/ (lexical, rrf, semantic, text, engine) | KEEP | Generic hybrid search. Structural ranking switches to KPI ids |
| steward/decision/minhash.py | KEEP | Duplicate detection on names/descriptions |
| steward/llm.py, prompts.py | KEEP | Claude + Gemini clients; Gemini path = MLH Gemini tick. Add a local (Ollama, OpenAI-compatible) client for the interviewer |
| steward/governance.py | KEEP, extend | Overlay writes, reject needs reason, CREATE needs owner (= RULE-003). Add actions: retire, consolidate, migrate, reassign owner |
| steward/explain.py | KEEP, extend | Template-then-LLM-rephrase with "don't change facts" is right. Add rule-ID + record-ID citations (RULE-008) |
| steward/pipeline.py, __main__.py | KEEP | Entry points; add `rescue(asset_id)` and expert mode |
| steward/models.py | CHANGE | Artifact gains: platform, workspace, model_id, product_scope, market_scope, kpi_ids, endorsement (certified/promoted/none), lifecycle, usage (views, unique users per month), model refresh_status, signals, lineage. ParsedQuestion becomes the Intent object: + role, decision, cadence, unmapped_terms, conflicts, confidence |
| steward/catalog.py | REWRITE | Load the xlsx (Analytics_Assets + Owners + Asset_KPI_Map + Asset_Usage + Semantic_Models + Lineage + Signals + DQ) instead of JSON |
| steward/linking.py, decision/conflicts.py | REWRITE core | Formula-string matching doesn't exist in the data pack (no formulas). Resolve by **KPI id -> canonical_metric + definition_status/approval_status**. A metric counts only via the approved KPI id; variants raise a conflict card. Handles the 4 duplicate-name KPI pairs |
| steward/decision/signals.py | CHANGE | Coverage: product/market scope instead of filters/dimensions (region -> markets rollup, "All Pharma"/"Global" = breakdown available). Trust: certified 0.4 / promoted ~0.25, active owner (Owners.status), model refresh healthy/warning/failed, real unique users, open high signals |
| steward/decision/engine.py | CHANGE | Keep REUSE/EXTEND/CREATE/CLARIFY for questions; attach lifecycle flags to candidates (consolidate, migrate per RULE-006, retire) |
| steward/health.py | CHANGE | Stale-by-date -> usage tiers (153 assets < 1,000 views Jan-Oct); no_owner must include the 65 inactive-owner assets; add certified-on-failed-refresh (16), duplicate clusters, Tableau backlog re-triage |
| steward/query_parser.py | CHANGE | Drop Russian quarter regex; add unmapped-term tracking; becomes the back half of the interview |
| catalog/*.json | DROP | Replaced by the data pack. metrics.json pattern survives as a hand-written synonym file for the 18 canonical metrics |
| tests/golden_questions.json | REWRITE | Contract idea is perfect; rebuild on real Business_Requests (10 templates) + REQ-0001 trap + AST-0091 orphan |
| docs/work-plan.md stage 2 | DROP | "Grow the catalog across Crop Science, Consumer Health..." is out of scope and unnecessary |
| docs/demo-script.md | REWRITE | Same 5-beat structure, data-pack records |
| app.py | KEEP, extend | Tabs Ask / Health / Journal / Catalog stay. Add: interview chat (+ voice), KPI disambiguation card, evidence cards with IDs, lineage impact, spec preview, Orphan rescue |

## Missing vs the brief and Panu's slide
- Interview / grill-me loop (CLARIFY is currently a dead end), voice, local LLM.
- DashboardSpec + render_preview (+ .PBIP skeleton) for CREATE (work-plan 4.4 mentions a draft spec only).
- Lineage downstream impact (RULE-004), Tableau->Power BI rationalisation (RULE-006), orphan-rescue entry point.

## Rough effort (one person each, parallel)
xlsx loader + models: 2-3 h · KPI-id resolution + conflicts: 1-2 h · trust/coverage/health on real fields: 2 h ·
golden set on data pack: 1-2 h · interview + intent object: 3-4 h · spec + preview: 3 h · voice: 2 h.
