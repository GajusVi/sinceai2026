id: 1107-122105-margiris-to-gajus
from: margiris
to: gajus
kind: question
created: 2026-11-07 12:21
re: 
---
DONE eval v1 (1b559bd): first run on Martynas's 25 hand-labelled rows, nothing tuned. Hold-out 22/25 = 88%, REUSE 4/4 with the right asset, false-REUSE 0 of 69 labelled non-REUSE cases (REUSE precision 1.0), all 73 labelled cases 95.9%. ESCALATE (verdict contract, yours): 3 misses are label-vs-contract questions. (1) H-01 'global Nubeqa dashboard: sales growth, forecast variance, market access': label CREATE (no Power BI asset covers more than 1 of 3), engine EXTEND AST-0335, and your golden_datapack.json also says EXTEND. Which is right: what coverage share makes a partial match EXTEND instead of CREATE? (2) H-05/H-06 finance dashboard where KPI-034 and KPI-039 have no data: label NOT_FEASIBLE, engine EXTEND AST-0015 with those two KPIs as labelled gaps (the plan's 'gap, never a number'). Options: A keep the engine (EXTEND with labelled gaps) and change the labels to match; B return NOT_FEASIBLE when any requested governed KPI has no data. I recommend A (the user still gets the 1 feasible KPI and an honest gap); labels then say EXTEND. I will not touch thresholds or labels until you decide.
