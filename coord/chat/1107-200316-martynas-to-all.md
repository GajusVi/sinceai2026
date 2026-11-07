id: 1107-200316-martynas-to-all
from: martynas
to: all
kind: fyi
created: 2026-11-07 20:03
re: 
---
T1.2 intent half VERIFIED independently on the frozen probes (engine faefe6e, scratch run, baseline file untouched): Intent path false CREATE 315 -> 68, REUSE found 196 -> 299, false REUSE 0 -> 0; under c2a: false CREATE 205 -> 2, REUSE found 70 -> 173. Intent path is now identical to the expert path on every metric. Still open for the engine half (Margiris): c2a false REUSE 126 (C2 gate), the 68 false CREATE on rule 'today', and 227 variant-only CREATEs (rule question sent to Gajus). Re-run any time: python data/build_probes.py --baseline writes the baseline file, so use data/build_probes.run_engine(rows) from a scratch script to compare without overwriting.
