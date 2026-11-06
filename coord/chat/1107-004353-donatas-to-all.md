id: 1107-004353-donatas-to-all
from: donatas
to: all
kind: fyi
created: 2026-11-07 00:43
re: 
---
HISTORY REVIEW Donatas: DONE: chat Ask tab, evidence cards, Reset demo, AppTest smoke (5af7fb9); Orphan rescue tab on data pack + Governance.propose + 2 app tests (d85d2e7). Tests 67 passed, 1 xfailed. IN PROGRESS: nothing open; A3 KPI card + wiring to real decision.evidence = 0%, Saturday, files frontend/steward_app.py. KNOWN ISSUES: (1) steward.health() ~45 s on the 360-asset data pack, stack ends in steward/linking.py:33 scan via health.py:40 _features, likely one linking scan per asset; workaround in my file: health tab computes on a button and caches. (2) Not yet seen in a real browser: make bayer only covered by AppTest. (3) Expert-mode toggle in the sidebar has no behaviour yet; Ask tab still shows FAKE_EVIDENCE (labelled Sample) until a decision carries evidence. (4) make lint auto-fixes other owners files (docs/vendor, steward/decision/minhash.py): run ruff on your own files only. NEEDS: Margiris, health() under 2 s, by Sat 12:00 checkpoint; Gajus, decision on JournalAction.PROPOSED (escalated). LOCAL DECISIONS not yet in NOTES.md: usage tier in Orphan rescue = bottom/top 20% of average monthly unique users (display only, matches BUILD_PLAN 2.2 idea); proposals are logged as action=approved, verdict=CLARIFY, question prefix PROPOSAL (not applied).
