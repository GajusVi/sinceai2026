id: 1107-113644-margiris-to-gajus
from: margiris
to: gajus
kind: done
created: 2026-11-07 11:36
re: 
---
DONE L6 (0b08ae1): steward/health.py on the data pack now uses the BUILD_PLAN 2.2 rule via lifecycle.estate(): 21 retire candidates (old rule said 142). CatalogHealth gains human_review, retire_funnel (360 > 354 old enough > 74 low use > 62 quiet > 21 with a reason > 21 not sole critical) and ownership counts that match 03_DATA_PACK exactly (65 inactive + 21 no owner, tiers 23/21/21, 16 certified on failed refresh). Sample catalog untouched, 311 tests green. Ask for the owner of frontend/steward_app.py: show retire_funnel + ownership in the Catalog health tab (its 'under 1,000 views' headline is not the retire rule). Question: is L11 (lint hardening: RULE-001 Jaccard on real search, RULE-004 lineage impact) still wanted, or cut? Otherwise I am free after M5.
