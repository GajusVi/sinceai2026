id: 1108-021556-martynas-to-all
from: martynas
to: all
kind: done
created: 2026-11-08 02:15
re: 
---
WINDOWS TRIAL BUILD PASS (Martynas, on main 5e74680, 02:04-02:14): build 10 min 07 s, dist\BI Steward 459 MB / 12,707 files. Self-test run 1 (cold) PASS: workspace after 12.4 s, signed in, log out ok. Run 2 (warm) PASS: workspace after 5.5 s. So the self-test race fix (e537949) holds on a cold start, streamlit-searchbox 0.1.24 and the dark design bundle fine. PyInstaller warnings are the harmless kind only (matplotlib not installed for plotly/pandas plotting extras; hidden imports pycparser.lextab/yacctab and scipy.special._cdflib not found); no 'No module named' for our code. Donatas (team lead now): the FINAL Windows build is mine after your freeze call: tell me the commit to build from (or 'build from main'), I need ~12 min + zip + sha256 for Margiris; run it after OVERVIEW lands or after your 04:00 on/off decision, whichever you choose. I also keep the OVERVIEW switch in mind: my pbip.py side already handles a spec without span/row unchanged.
