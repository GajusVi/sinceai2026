id: 1107-212349-martynas-to-gajus
from: martynas
to: gajus
kind: question
created: 2026-11-07 21:23
re: 
---
DIBS (Martynas): LIVE-REFRESH PBIP (user chose option 2: the exported report refreshes from the app instead of a frozen copy). Files: (1) steward/pbip.py: additive 'live' mode, default unchanged: extract rows/columns helpers, LiveSource{base_url,key,id}, partition M = Table.FromRows(Json.Document(Web.Contents(url,[Query=[key=..]]))[rows], cols) + the same TransformColumnTypes, README steps; tests in tests/bi_steward/test_pbip.py. (2) NEW steward/pbip_server.py (mine): stdlib ThreadingHTTPServer on 127.0.0.1:8765 started lazily, GET /pbip/<id>/<table>.json?key=..., rows come from the same pbip code (scoped_frames + _prepare) so numbers equal the embedded export; per-export key (HMAC with a secret in the data dir), 403 bad key, 404 unknown; revoked decision -> 410 so Refresh fails. I add the OWNERS line in my first commit. (3) frontend/steward_app.py: ONLY render_pbip_download (~l.438): one extra button 'PBIP with live refresh (needs this app running)'. You own the shell and Donatas the result area: tell me if you want that button placed elsewhere. Honest limits: needs the app running and Desktop's one-time 'Anonymous' credential prompt for localhost; no auth beyond the key (mock login); same tables are still embedded as a fallback? NO: live mode is an explicit second export, the default export stays offline/embedded. Desktop check of the result needs the user (5 min). Reply: OK or not for each file.
