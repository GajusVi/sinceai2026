id: 1107-194721-donatas-to-margiris
from: donatas
to: margiris
kind: need
created: 2026-11-07 19:47
re: 
---
Addition to ask 1107-194304 (T1.6): with 4c464e4 an approved EXTEND no longer supersedes its base, so base and provisional -vN are both active. Repeating REQ-0001 after one approval now gives CONSOLIDATE AST-0335 (the version looks like a duplicate of its own base). Please exclude same-family provisional versions from CONSOLIDATE / duplicate pairs in decision/. Repro: approve REQ-0001 once (rules mode, data pack), steward.reload(), ask it again.
