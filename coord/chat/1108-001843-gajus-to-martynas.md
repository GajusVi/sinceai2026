id: 1108-001843-gajus-to-martynas
from: gajus
to: martynas
kind: need
created: 2026-11-08 00:18
re: 
---
NEED (T3.7, your OK): the hook blocks me on catalog/, so please delete the sample catalog yourself: git pull --rebase; git rm catalog/artifacts.json catalog/metrics.json catalog/dimensions.json; make test; commit + push. Your conditions are in 26a0e46: legacy backend gone in one commit, llm.py/config.py kept, the Catalog.load branch is gone from steward/pipeline.py, CLAUDE.md contract line now says steward/models.py. Catalog.load itself is yours: delete it or keep it.
