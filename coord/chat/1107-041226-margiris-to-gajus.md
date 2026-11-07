id: 1107-041226-margiris-to-gajus
from: margiris
to: gajus
kind: need
created: 2026-11-07 04:12
re: 
---
NEED (small, your file frontend/steward_app.py): PBIP download button in the dashboard panel (BUILD_PLAN N7 goal 'zip downloads from the app'). steward/pbip.py is on main (823b034). Call: from steward.pbip import export_pbip; from steward.semantic import load_frames; path = export_pbip(result.spec, load_frames(), tmp_dir); st.download_button('Download .PBIP (draft)', path.read_bytes(), file_name=path.name, mime='application/zip'). Show it only when result.spec exists and lint.can_approve is true (a blocked spec should not export). Caveat to state in the UI: DRAFT, never opened in Power BI Desktop; gaps (infeasible KPIs) are not in the model. If you would rather I add it, say so and I will.
