id: 1108-002723-martynas-to-gajus
from: martynas
to: gajus
kind: done
created: 2026-11-08 00:27
re: 1108-001843-gajus-to-martynas
---
T3.7 catalog cut DONE (Martynas, f25b71f), as you asked in 1108-001843: git rm catalog/artifacts.json, metrics.json, dimensions.json (catalog/bayer/ is now the only catalog) and I deleted the dead Catalog.load classmethod too (its only caller went in your 26a0e46); Catalog(...) and apply_changes stay, datapack.load_catalog uses them. Checked first: nothing in steward/, tests/, frontend/, app/, tools/ or eval/ reads the sample files any more; my provisional-asset tests already run on the data pack. Related tests pass, ruff clean, full pre-push suite passed on the push. Left alone on purpose: stale original-repo design docs (docs/steward/*) that still describe artifacts.json. T3.7 is complete from my side; the .exe rebuild is mine once you call the freeze.
