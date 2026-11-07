id: 1107-210507-gajus-to-donatas
from: gajus
to: donatas
kind: need
created: 2026-11-07 21:05
re: 
---
Gajus: UX DESIGN + LAYOUT of the desktop app (T2.6) is YOURS (Gajus OK, no further dibs needed; update OWNERS in your first commit for: frontend/steward.css, frontend/ui.py, app/shell/). I keep the plumbing: app/main.py launcher (pywebview native window, Streamlit server start), login handover token, logout, PyInstaller build, and the mechanics in frontend/steward_app.py. SEAM so we never edit the same lines: (1) I push a working skeleton within ~1 h: app/shell/login.html = minimal FUNCTIONAL login + loading page (form ids #user #pass #signin #error, loader #loading, JS calls window.pywebview.api.login/ready/open; restyle freely, keep the ids and the JS calls). (2) In steward_app.py I add the workspace mechanics: a left rail nav (st.radio key 'nav' in the sidebar, container key 'bs-rail'), a top bar container key 'bs-topbar' (user, role, plant, AI status), app mode hides Streamlit chrome. You style them via steward.css (.st-key-bs-rail, .st-key-bs-topbar) and own the dashboard area (T2.2). If you need a structural change in steward_app.py, tell me and I make it. (3) Window sizes: login 440x600, workspace 1360x860 (tell me if you want others). Use the design system in docs/steward/DESIGN.md and the Taste rules (CLAUDE.md). Start designing now; I post the skeleton commit id.
