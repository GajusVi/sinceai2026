id: 1107-004949-margiris-to-gajus
from: margiris
to: gajus
kind: question
created: 2026-11-07 00:49
re: 
---
ESCALATE: a request that says 'global' currently matches an EMEA-only asset (REQ-0001 -> AST-0143, EXTEND). Options: A) treat 'global' as market=Global filter, so region/country-locked assets become incompatible (REQ-0001 then likely EXTEND on AST-0015/AST-0335); B) leave it and show a scope-mismatch warning only. I recommend A because BUILD_PLAN 2.4 says a region asked needs a Global or region-level asset. It changes verdicts, so I will update golden_datapack.json in the same commit.
