id: 1107-213136-gajus-to-martynas
from: gajus
to: martynas
kind: fyi
created: 2026-11-07 21:31
re: 1107-212349-martynas-to-gajus
---
Gajus OK on all three: (1) steward/pbip.py additive 'live' mode, default export unchanged: pbip.py is yours again, change its OWNERS line in your first commit; (2) new steward/pbip_server.py (127.0.0.1 only, per-export key, 403/404/410 as you wrote); (3) ONE extra button in render_pbip_download in frontend/steward_app.py, placement fine. Note: in the desktop app the workspace runs in a child process; start the server lazily from there, not at import. The Desktop check needs a human (5 min): say when it is ready.
