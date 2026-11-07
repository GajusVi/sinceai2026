id: 1107-195657-martynas-to-all
from: martynas
to: all
kind: done
created: 2026-11-07 19:56
re: 
---
T1.3 baseline FROZEN (55f681d), before T1.2: data/build_probes.py (independent oracle, no engine imports, guarded by a test) + data/holdout/probes.jsonl (980 probes, labels under 'today' and 'c2a') + probes_baseline.json (engine 95b7c14). Re-run: python data/build_probes.py --baseline (30 s, both paths). Baseline: expert path REUSE found 299/434, false CREATE 68; Intent path REUSE found 196/434, false CREATE 315 (32%). Under C2=A the engine has 126 false REUSE (not implemented yet), 70 on assets the engine itself calls RETIRE. Margiris: score both paths with this in eval; target after T1.2: Intent-path false CREATE near the expert path, false REUSE 0 under c2a. T1.4 done too (e0557c9): 10/12 measures matched in Desktop; KPI-031/054 were fractions in DAX (0.2, 0.1), fixed to percentage points + a test for every % KPI; re-exported check at C:\SinceAI\pbip_all_measures.
