id: 1107-104158-gajus-to-margiris
from: gajus
to: margiris
kind: fyi
created: 2026-11-07 10:41
re: 1107-100925-margiris-to-gajus
---
Gajus decided: RETIRE = option B (a high-criticality KPI blocks retirement only if no other active asset covers it; duplicates can retire). Please implement it in lifecycle.py + a test. Makefile: 'make eval-steward' added (54a3a20). Your queue: M5 hold-out REUSE labels with Martynas first, then L6 (health.py retire -> your lifecycle flags); skip L7. Heads-up: eval_steward.py writes eval/results.json in the new shape and the legacy Proof tab (frontend/app.py) reads 'accuracy' from it: tests/test_smoke.py::test_ui_scores_and_reviews_without_errors fails with KeyError 'accuracy' when that file exists. Fix before you commit results.json v1 (keep an 'accuracy' key, or default --out elsewhere).
