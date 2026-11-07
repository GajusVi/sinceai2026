id: 1108-011633-martynas-to-all
from: martynas
to: all
kind: done
created: 2026-11-08 01:16
re: 
---
REVOKED PATH VERIFIED IN POWER BI DESKTOP (Martynas + user): after the decision behind a live PBIP export was withdrawn (pbip_server.revoke), Refresh failed with: Web.Contents failed to get contents from 'http://127.0.0.1:8765/pbip/<id>/fact_pmm.json?key=...' (410): Gone. A withdrawn approval stops an exported report from refreshing; before, it loaded 200. So the whole loop is now seen on a real machine: approve -> export -> Refresh pulls the governed rows (4 cards match) -> withdraw -> Refresh refuses. Pitch line: 'the file stays tied to the approval'. Honest limit: Desktop shows only '(410): Gone', not our explanation, and the cards keep the last loaded values; the README inside the export now says so. Wiring revoke to a real action (e.g. governance withdrawing a decision, or a provisional asset expiring) is not done: pbip_server.revoke(data_dir, spec_id) exists for Donatas/Gajus to call.
