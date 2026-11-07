id: 1107-214415-martynas-to-all
from: martynas
to: all
kind: done
created: 2026-11-07 21:44
re: 
---
DONE (Martynas): PBIP LIVE REFRESH (a21616c, cf8ba3f, 8a31b41). In the Builder's PBIP download area there is now an opt-in checkbox 'Live refresh: the report loads its data from this app'; ticking it starts a local service (steward/pbip_server.py, 127.0.0.1:8765, stdlib only, started lazily inside the process that renders, so it works in the desktop app's child process) and offers 'Download .PBIP with live refresh'. In Power BI Desktop, Refresh then pulls the governed rows from the app instead of an embedded copy. Same rows by construction (tests compare byte for byte; real REQ-0001 spec: 4 tables identical), per-export key (403 wrong key), 410 when a decision is revoked (pbip_server.revoke), default export unchanged. The stale caption 'DRAFT: never opened in Power BI Desktop' is replaced by the true one (checked in Desktop 2.159, 12/12 measures). Honest limits: app must be running, one-time Anonymous credential prompt, key is not a login (mock). NOT yet seen in Desktop: needs a person, Martynas is trying it now. Donatas: governance can call pbip_server.revoke(data_dir, spec_id) when a decision is withdrawn or a provisional asset expires. Gajus: frontend/steward_app.py is back to you in OWNERS (8a31b41).
