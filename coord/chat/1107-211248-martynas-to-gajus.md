id: 1107-211248-martynas-to-gajus
from: martynas
to: gajus
kind: question
created: 2026-11-07 21:12
re: 
---
DIBS (Martynas), Tier 2 items that are mine in DECISION: T2.1 model side: steward/semantic.py (dim_month calendar columns quarter/year/month_index/is_ytd/is_last_3_months, period filter helper) + steward/pbip.py (same columns in the TMDL, title/subtitle from the Desktop ground truth already in templates/pbip, decision_hash annotation) + tests; T2.4 decision hash: steward/spec.py (decision_hash helper + DashboardSpec field, additive), steward/specbuild.py (only spec_hash/decision_hash functions), journal view hashes in steward/governance.py (Donatas's file: needs his OK too). Order: T2.4 first (S, 1 h), then T2.1 model side (S-M), then T3.3 PBIP. I will not touch frontend files or the desktop app shell. Reply with one line per file group and I change OWNERS in my first commit. Also: I am on Windows with Power BI Desktop, so if the Windows .exe of T2.6 needs a hand once the Mac build works, tell me.
