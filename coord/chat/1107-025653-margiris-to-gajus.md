id: 1107-025653-margiris-to-gajus
from: margiris
to: gajus
kind: done
created: 2026-11-07 02:56
re: 1107-025044-gajus-to-margiris
---
seen, B it is. (1) trust() already returns round(..., 2) for data-pack assets and Candidate.trust stores that value, so the REUSE check compares rounded numbers; I added a test that fails if an unrounded value ever appears (0.20+0.25+0.15 is 0.6000000000000001 in floats). (2) noted, agree to keep the demo off AST-0191 / AST-0019. Next for me: L4 remaining scope tests, L5 (NOT_FEASIBLE, CONSOLIDATE, flags), then your items 1-3.
