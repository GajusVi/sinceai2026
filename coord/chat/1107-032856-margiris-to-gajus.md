id: 1107-032856-margiris-to-gajus
from: margiris
to: gajus
kind: question
created: 2026-11-07 03:28
re: 
---
ESCALATE (N6 CONSOLIDATE precedence): where does CONSOLIDATE sit relative to REUSE/EXTEND? Your brief: '>= 2 compatible candidates, same product scope, canonical-KPI Jaccard >= 0.6 -> keeper = most trusted, others listed'. On the data pack duplicates are common (125 duplicate pairs in health()), and the sample-catalog golden 'Fungicide margin in EMEA' (two stale copies, certified one must win) expects REUSE. Options: A) CONSOLIDATE only when no cluster member is REUSE-eligible (coverage 1.0, trust >= 0.6, Power BI) but >= 2 members cover the question: the keeper becomes the base of the merged dashboard. When a member IS REUSE-eligible, verdict stays REUSE and the duplicates are a flag + RULE-001-style evidence ('2 duplicates, consolidate in the estate queue'). B) CONSOLIDATE wins whenever a cluster of >= 2 exists, REUSE only for a lone asset (will change several goldens, incl. the sample one). C) Verdict never CONSOLIDATE for a question; only the estate-health door (W10) produces CONSOLIDATE specs. I recommend A: a question should be answered by the best asset, and the duplicates ride along as a flag; the merged dashboard comes up when nothing is good enough on its own. Meanwhile I build the cluster detection (shared by all three options) and NOT_FEASIBLE when semantic.feasibility lands. Please also note: first N5/N7 done and pushed.
