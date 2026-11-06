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
## T3 (D4, 01:30-03:00) goldens on the data pack with Margiris: tests/bi_steward/golden_datapack.json (REQ-0001 → CLARIFY first).
