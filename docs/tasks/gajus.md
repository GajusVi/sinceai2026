# Gajus: tonight 00:05 → 03:00 (intent contract + data-pack loader)

Your files: steward/intent.py, steward/datapack.py (new), docs/. pipeline.py is shared.

## T1 (C2, 00:05-00:25) `steward/intent.py`
`Intent`: role, decision_supported, cadence, products, markets, regions, metric_ids (canonical ids from catalog/bayer/metrics.json),
unmapped_terms, grain ("month"|"quarter"), comparison ("target"|"forecast"|"prior"|None), audience, conflicts,
confidence: dict[str, float], mode ("novice"|"expert"|"rescue"), plus `to_parsed_question()` adapter so the current engine runs on it.
Stop rule helper `is_complete()`: products, markets or regions, ≥ 1 metric, decision_supported, all confidence ≥ 0.7.

## T2 (D1, 00:25-01:30) `steward/datapack.py`: load the xlsx into 360 `Artifact`s
Join Analytics_Assets + Owners (role, scope, status, successors: same role+scope active first, then same role) + Asset_KPI_Map +
Asset_Usage (only months ≥ created month; earlier rows → data_quality "USAGE_BEFORE_CREATED") + Semantic_Models (refresh_status, endorsement) +
Lineage_Edges (upstream/downstream) + Governance_Signals + Data_Quality. last_refreshed = last_modified (labelled). Name-vs-scope mismatch → data_quality.
Hook in `steward/pipeline.py`: if `STEWARD_CATALOG=datapack` (or catalog_dir points to the xlsx) use the data-pack catalog with
catalog/bayer/metrics.json + dimensions.json. Tests: 360 assets, 94 Tableau, 21 missing owners, 65 inactive-owner assets, 266 Power BI.
## T3a (00:05-01:15) request intake = trap 1 as a feature, `steward/intent.py`
`intent_from_request(row, catalog)`: parse the request text, compare with the row's product_context / market_context.
Different product → `conflicts += ["text says Nubeqa, request field says Beyonttra"]`; text says global or a region while
market_context is a country (or the reverse) → conflict. Any conflict → CLARIFY, with the conflict as a blocker Evidence.
Test on REQ-0001 (text Nubeqa/global vs Beyonttra/EMEA) and on Martynas's data/holdout/requests_intent.jsonl `metadata_conflict` labels
(65 of 75 product-naming requests should conflict).
## T3b (01:15-03:00) goldens on the data pack with Margiris: tests/bi_steward/golden_datapack.json
REQ-0001 with metadata → CLARIFY first. Do NOT lock its post-clarification verdict until Margiris's L2 lands
(today CREATE is only an artefact of the KPI placeholder; likely EXTEND on AST-0335 or AST-0015, 1 of 3 canonical KPIs).
