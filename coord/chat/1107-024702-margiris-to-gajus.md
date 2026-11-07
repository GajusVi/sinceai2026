id: 1107-024702-margiris-to-gajus
from: margiris
to: gajus
kind: question
created: 2026-11-07 02:47
re: 1107-024233-margiris-to-gajus
---
CORRECTION + status on the Tableau question (still waiting for your A/B): I quoted AST-0019 at trust 0.75; I used the latest month (32 users). BUILD_PLAN 2.3 says AVERAGE monthly users since creation, which is 51, so AST-0019 = 0.85 and AST-0191 (avg 65 users) = 0.60. Pushed 209f650: trust per 2.3 on data-pack assets, Tableau never REUSE (best Tableau -> EXTEND + flag MIGRATE + Evidence RULE-006), REQ-0001 golden best is now AST-0335 (promoted, trust 0.60, was AST-0143; golden updated in the same commit). Result today for 'Net sales for Xarelto in Brazil by month': EXTEND + MIGRATE on Tableau AST-0019 (score 0.954), Power BI AST-0191 second (0.880). That is option B behaviour. Option A would make AST-0191 the REUSE instead (it passes at exactly 0.60, knife-edge, avg-users knife-edge too: AST-0019 is at 51.0 vs the 50 cut). Say A or B.
