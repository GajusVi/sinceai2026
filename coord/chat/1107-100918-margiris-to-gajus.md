id: 1107-100918-margiris-to-gajus
from: margiris
to: gajus
kind: done
created: 2026-11-07 10:09
re: 
---
DONE queue item 2 (f7eeff4): steward/decision/lifecycle.py, wired in decide() for the data pack only. Flags: FIX_REFRESH (RULE-005, cites model+asset), REASSIGN_OWNER tiers a/b/c (RULE-003; counts match 03_DATA_PACK: 23/21/21 + 21 no owner), RETIRE/HUMAN_REVIEW (RULE-004), MIGRATE backlog evidence (RULE-006, 'claim not fact'). Thresholds in config.py. 15 tests in test_lifecycle.py, full suite green, goldens unchanged. Not done: L6 (replace health.py retire rule), L7 lineage impact.
