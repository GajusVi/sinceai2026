id: 1107-100925-margiris-to-gajus
from: margiris
to: gajus
kind: question
created: 2026-11-07 10:09
re: 
---
ESCALATE: RETIRE never fires with the literal rule 'no high-criticality KPI'. 43 of 56 KPIs are high, so 358 of 360 assets carry one. Result today: 0 RETIRE, 21 HUMAN_REVIEW (they pass every other check). Options: A keep literal (honest, but the RETIRE flag never shows in the demo; the 21 go to HUMAN_REVIEW); B count a KPI as critical only if no other active asset covers it, so duplicates can retire; C keep A but show the 21 as 'retire candidates, human review' in the UI. I recommend B because it matches the intent (do not orphan a critical KPI). Kept A in code meanwhile.
