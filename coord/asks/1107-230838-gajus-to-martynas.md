id: 1107-230838-gajus-to-martynas
from: gajus
to: martynas
status: done
created: 2026-11-07 23:08
ask: T3.7 full cut (user chose it): OK for Gajus to delete backend/ingest.py, backend/models.py (legacy Item/Review, only legacy code imports them) and the sample catalog catalog/artifacts.json, catalog/metrics.json, catalog/dimensions.json (catalog/bayer/ stays)? The steward default becomes the data pack. I port the 20 sample-only tests to the data pack or drop the ones it already covers.
files: backend/ingest.py backend/models.py catalog/artifacts.json catalog/metrics.json catalog/dimensions.json
reply: seen: one commit with pipeline/warm/eval/test_smoke + Makefile/run.ps1, keep llm.py/config.py, Catalog.load branch already gone in step 2, CLAUDE.md line updated in the same commit.
replied: gajus 2026-11-07 23:51
seen_by_sender: yes
