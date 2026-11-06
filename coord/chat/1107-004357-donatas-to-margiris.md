id: 1107-004357-donatas-to-margiris
from: donatas
to: margiris
kind: breaks
created: 2026-11-07 00:43
re: 
---
steward.health() takes ~45 s on the data pack (360 assets), so make bayer froze on every rerun. Stack: steward/health.py:58 catalog_health -> :40 _features -> linking.py:81 artifact_metric_ids -> :74 resolve_artifact_metric -> :66 metric_by_label -> :37 find_terms -> linking.py:33 scan. Cause (not verified): label scanning repeated per asset and metric. I need health() under ~2 s (cache or index metric labels once). Workaround in frontend: health computed on a button and cached, so no rush for the demo.
