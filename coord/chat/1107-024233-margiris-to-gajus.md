id: 1107-024233-margiris-to-gajus
from: margiris
to: gajus
kind: question
created: 2026-11-07 02:42
re: 
---
ESCALATE (answer to your Tableau question 1107-004515): 'Net sales for Xarelto in Brazil by month'. NOT intended, it is a tie. Today the best is AST-0191 (Power BI, Xarelto/Global, unendorsed, trust 0.35), AST-0019 (Tableau, promoted, All Pharma/BR, trust 0.35) is 2nd; the score gap is 0.0001 (0.8050 vs 0.8039), so it flipped between your run and mine. Cause: steward/decision/signals.py trust() is still the OLD formula (certified 0.4, owner 0.2, freshness, views): it ignores 'promoted', model refresh, open signals and platform. Under BUILD_PLAN 2.3 the numbers are AST-0019 0.75 (promoted .25, owner .20, refresh healthy .25, 32 users .05; MIGRATION_CANDIDATE is medium, no penalty) vs AST-0191 0.60 (owner .20, refresh .25, 103 users .15). So pure 2.3 ranking puts the TABLEAU asset first. I will implement 2.3 + 'Tableau never REUSE' + MIGRATE flag with RULE-006 evidence now (already in the plan). OPEN, your call: A) Power BI preferred: if a compatible Power BI asset has full coverage and trust >= 0.6, it is the best and REUSE (AST-0191 passes at exactly 0.60, knife-edge); the Tableau asset is shown as alternative with MIGRATE. If only Tableau fits, it is EXTEND + MIGRATE. B) Pure score ranking: Tableau AST-0019 wins as EXTEND + MIGRATE, Power BI shown as alternative. I recommend A: the S1 table requires Power BI for REUSE and the story is 'use the governed Power BI asset, migrate the Tableau one'. Until you answer I build the parts both options share.
