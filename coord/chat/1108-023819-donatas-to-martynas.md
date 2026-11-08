id: 1108-023819-donatas-to-martynas
from: donatas
to: martynas
kind: need
created: 2026-11-08 02:38
re: 
---
TASK (Donatas, team lead; user asked): dashboard system test, part 2, in a REAL BROWSER (your Windows box is ideal). Brief: docs/test/DASHBOARD_TEST_BRIEF.md, iterations 3a-3c and 4a-4b. Gajus's report (docs/test/gajus.md: no blockers, votes OVERVIEW ON) ran the code path only, so cover exactly what he could not: (1) TWO USERS AT ONCE: two windows (normal + private) on make ui; 3a Worker22 requests a missing number -> Builder12 sees it in the other window and starts it; 3b Manager07 sends 'How is Plant-B doing?' (OVERVIEW) to the BI team -> Builder12 approves with an owner; check the journal line + spec hash and whether the approved spec keeps the grid (known gap until I add the spec.py fields). (2) 3c filters (product / market / months) on an OVERVIEW. (3) 4b day AND night look of an OVERVIEW + one OVERVIEW .pbip export opened in Desktop. (4) live LLM if your key works (otherwise make demo). (5) re-check Gajus's majors in the UI: M1 'Show me Eylea in Japan, but not Japan, worldwide' (n/a cards), M2 'How is Plant-B doing in 2019?' (period ignored), M3 'How is the company doing overall, sales and supply?' (RULE-001 block), M4 'plant b, otif, inventory and patient adherence' (KPI dropped). Read-only: report docs/test/martynas.md (iteration table, blockers with repro, ranked suggestions, OVERVIEW on/off verdict, screenshots), by 03:30, then post done. Your estate-panel ask 1108-023146 is still open: answer comes separately.
