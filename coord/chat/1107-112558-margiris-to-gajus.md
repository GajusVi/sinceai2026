id: 1107-112558-margiris-to-gajus
from: margiris
to: gajus
kind: done
created: 2026-11-07 11:25
re: 
---
DONE RETIRE option B (df5ca66): a high-criticality KPI blocks RETIRE only when no other active asset carries it. Result: 21 RETIRE candidates, 0 HUMAN_REVIEW; a test proves retiring all 21 leaves every high-criticality KPI with at least one report. eval_steward.py now also writes top-level n / accuracy / macro_f1 / misses so the legacy Proof tab does not KeyError; I will commit results.json v1 after M5. Next for me: M5 with Martynas, then L6.
