id: 1107-163850-gajus-to-margiris
from: gajus
to: margiris
kind: need
created: 2026-11-07 16:38
re: 
---
NEW TASK, MUST do now (with the other one of you two): make the dashboard dynamic. Today specbuild fills a fixed template per verdict. Target: the system decides the hierarchy of the data (what leads, what is secondary, what goes to detail), how to show each piece (tile, trend, ranking, table, gap) and anything else that matters for personalisation. Step 1, before any code: discuss the design with your AI and agree it together. Inputs: the intent, the verdict and KPIs, the data shape, and who is asking (steward/auth.py, 8d4219e: role worker/management/builder, plant, location, department; workers get reuse only, see steward/worker.py). Fixed rails: the verdict stays rule-based code; the LLM proposes the layout, code validates it (lint) and falls back to a deterministic layout so make demo works offline; an infeasible KPI stays a labelled gap, never a number. Post one short proposal on the board (who decides what, the layout contract, which files change, how we test it), then call dibs on the files. Your angle: the decide side (LLM layout proposal + validation). Parked: H-01, L11.
