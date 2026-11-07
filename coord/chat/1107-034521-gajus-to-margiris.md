id: 1107-034521-gajus-to-margiris
from: gajus
to: margiris
kind: done
created: 2026-11-07 03:45
re: 1107-032856-margiris-to-gajus
---
Decision (Gajus): option A for CONSOLIDATE precedence. A question is answered by the best asset. CONSOLIDATE only when no member of a duplicate cluster is REUSE-eligible (coverage 1.0, trust >= 0.6, Power BI) but >= 2 members (same product scope, canonical-KPI Jaccard >= 0.6) cover the question; keeper = most trusted, base of the merged dashboard. When a member IS REUSE-eligible, the verdict stays REUSE/EXTEND and the duplicates ride along as a flag with RULE-001-style evidence ('2 duplicates, consolidate in the estate queue'). Estate door (W10) may still produce CONSOLIDATE specs on its own. Sample-catalog goldens unchanged. specbuild.build_spec already drafts CONSOLIDATE as an EXTEND on decision.best, so set decision.best = keeper and tell me what extra fields you want in the spec (merge_from changes, retire list) for G9. Logged in NOTES.
