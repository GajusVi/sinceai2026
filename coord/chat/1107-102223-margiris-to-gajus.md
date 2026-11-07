id: 1107-102223-margiris-to-gajus
from: margiris
to: gajus
kind: done
created: 2026-11-07 10:22
re: 
---
DONE queue item 3 (2b512b0): eval/eval_steward.py. Run: STEWARD_CATALOG=datapack .venv/Scripts/python.exe eval/eval_steward.py (about 10 s with the 150-request estate run). Prints false-REUSE, accuracy, confusion matrix, intent F1, % without a new dashboard, lint pass rate, flag counts. First numbers: false-REUSE 0/48 but NO labelled case expects REUSE, so that proves little until M5 hold-out verdicts exist; intent 100% on the 40 tuned rows; estate (rules) 50 EXTEND + 100 CLARIFY of 150 = 33% without a new dashboard. Two asks: (1) Makefile is yours: please add 'eval-steward: STEWARD_CATALOG=datapack $(PY) eval/eval_steward.py'. (2) G11 headline numbers already come out of this script's estate section and your tools/compare_modes.py; unless you want more, I treat item 4 as covered once I add NOT_FEASIBLE gaps by KPI.
