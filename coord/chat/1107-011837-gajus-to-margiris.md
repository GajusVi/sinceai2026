id: 1107-011837-gajus-to-margiris
from: gajus
to: margiris
kind: done
created: 2026-11-07 01:18
re: 1107-004949-margiris-to-gajus
---
OK from Gajus: option A. A request that says 'global' is a scope filter: only Global-scope assets are compatible, single-country (and region-level) assets are not (BUILD_PLAN 2.4). REQ-0001 must stop picking AST-0143 (market_scope not Global). Update tests/bi_steward/golden_datapack.json in the same commit as the rule change, with the reason; the REQ-0001 'no metadata' case is EXTEND today. FYI steward/requests.py has its own 'global' regex for the intake check (text vs metadata); if you move a detector into linking.py I will switch to it. Logged in NOTES Decisions.
