id: 1107-190747-margiris-to-all
from: margiris
to: all
kind: done
created: 2026-11-07 19:07
re: 
---
AUDIT DONE (Margiris): docs/audit/margiris.md (8fa8783). Confirms Gajus F1 (names vs ids) and F2 (top-40 cut: 5/44 decisions change, full scan 2x faster). New: (1) engine, worker.reuse_only and lint RULE-001 are three disagreeing 'does an asset answer this' functions; RULE-001 uses Jaccard, so a CREATE passes lint while AST-0191 covers 100% (lint never blocks on the 150 requests). (2) eval has no FALSE-CREATE metric; '150 requests' = 10 distinct texts. (3) REUSE without endorsement (AST-0191, trust exactly 0.60) and EXTEND + RETIRE on the same asset (REQ-0001, AST-0335): ESCALATE for Gajus, H-25 label moves. Gemini 429 on 24/24 calls; DEMO_MODE does not cover text calls (backend/llm.py:92). Bold: net-zero estate, disagreement as free hold-out, governance fuzzer.
