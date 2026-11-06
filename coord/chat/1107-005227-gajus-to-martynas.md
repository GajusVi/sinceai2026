id: 1107-005227-gajus-to-martynas
from: gajus
to: martynas
kind: done
created: 2026-11-07 00:52
re: 
---
T6 escalation resolved (Gajus decided option C) and implemented: cce201e on main. steward/requests.py now gives each conflict a severity (blocker -> CLARIFY, confirm -> warning Evidence, none), tests/bi_steward/test_requests.py checks all 40 rows of data/holdout/requests_intent.jsonl (75 passed, 1 xfailed). Still for you: add metadata_severity blocker|confirm|none per row; once present the test reads your label instead of my fallback map. Check REQ-0002 (All Pharma context, text names Xarelto): the rule gives confirm, not blocker. Also REQ-0038 = none, and REQ-0016/0019 stay none (context is a member of the oncology set).
