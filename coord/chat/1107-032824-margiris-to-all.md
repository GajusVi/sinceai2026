id: 1107-032824-margiris-to-all
from: margiris
to: all
kind: done
created: 2026-11-07 03:28
re: 
---
N5 done (lint.py) + N7 TMDL half done (pbip.py), both pushed. LINT: from steward.lint import lint, can_approve; lint(spec, catalog) -> one LintResult per rule in fixed order (RULE-001..008, FOCUS, DATA), can_approve(spec) is False until spec.lint is filled and has no block. RULE-002 exceptions go in spec.provenance['exception:<KPI id>'] = reason. On Gajus's REQ-0001 fixture: 0 blocks, 1 warn (RULE-005: model SM-069 has no endorsement, audience is leadership). PBIP: from steward.pbip import export_pbip; export_pbip(spec, frames, out_dir) -> <out_dir>/<name>.pbip.zip (pbip + SemanticModel TMDL + Report/definition.pbir + data/*.csv + spec.json + README labelled 'draft, not opened in Power BI Desktop yet'). Gaps (infeasible measures) are never written to the model. Layout checked against Microsoft docs, NOT opened in Desktop. Missing: report visuals (Martynas), DataFolder path is a parameter the user edits. Next: N6 CONSOLIDATE + NOT_FEASIBLE when semantic.feasibility lands.
