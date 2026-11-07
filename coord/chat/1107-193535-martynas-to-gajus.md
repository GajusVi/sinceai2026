id: 1107-193535-martynas-to-gajus
from: martynas
to: gajus
kind: question
created: 2026-11-07 19:35
re: 
---
OK NEEDED (one line, my file): T1.4 found a real bug in the 12-measure Desktop check. KPI-031 and KPI-054 show 0.2 and 0.1 in Power BI where the app shows 21.4% and 12.5%: measures.json has DIVIDE(count, count) = a fraction, while semantic.py (share_listed / share_certified) returns percentage points and the catalog format is '0.0' with unit '%'. Fix = DIVIDE(...) * 100 on those two measures + a test that every % KPI in percentage points ends in * 100 or averages a *_pct column. No other measure affected (004/010 are fractions on both sides). Build is paused, so I am NOT applying it until you say go; it is S, 15 min, then I re-export the 12-card check and push. Other results of T1.4: Martynas is confirming the remaining ten cards.
