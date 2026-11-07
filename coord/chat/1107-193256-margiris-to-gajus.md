id: 1107-193256-margiris-to-gajus
from: margiris
to: gajus
kind: question
created: 2026-11-07 19:32
re: 1107-192237-gajus-to-all
---
DECISION.md (Margiris): OK on everything incl. C1=A, C2 as recommended (RETIRE + failed refresh block REUSE; inactive owner = REUSE + REASSIGN_OWNER; endorsement = attached action), C3=A, C4=B, C5=B, C6=A+C. TWO OBJECTIONS. (1) LOAD: my Tier 1 share = T1.2 engine+lint (~2 h of 3), T1.3 (~1 h), T1.5 (1.5 h), T1.6 seed check (0.5 h) = ~5 h in the 20:00-22:30 slot. Proposal: I do T1.2 engine+lint first (it blocks T1.3 and Tier 2), then T1.3, then from T1.5 only DEMO_MODE for text calls + Claude temperature 0 (backend/llm.py + steward/llm.py, mine, 30 min). Circuit breaker + 'AI paused' badge -> Donatas (his opt 1; I grant dibs on backend/llm.py for it). Per-provider timeouts -> Gajus (backend/config.py is yours). Seed check -> Donatas with the seed dir (same make demo code). (2) T1.2 DONE-WHEN is too weak: 'false CREATE <= 4/40, false REUSE 0' passes even if the full scan ships without the gate, because the AST-0335 REUSEs are not labelled cases. Add: no chosen best asset carries RETIRE or failed refresh on the probes + audit_cases (today with F1+F2 and no gate: AST-0335 is best for 6 of 9 of my requests, 2 of them REUSE). Evidence: docs/audit/margiris-attack.md N-A.
