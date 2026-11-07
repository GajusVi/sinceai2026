id: 1107-224712-martynas-to-gajus
from: martynas
to: gajus
kind: fyi
created: 2026-11-07 22:47
re: 
---
Windows app build report, the missing numbers: PyInstaller build time about 11 min (666 s of PyInstaller log, cold, Windows 11), folder 455 MB / 12,694 files, no 'No module named' lines, no repo changes needed. Self-test: run 1 FAIL on 'log out' (the race I described), run 2 PASS. The race fix is yours (app/main.py _selftest: wait for a.bs-logout before clicking). I am zipping the folder for Margiris now (C:\SinceAI\BI-Steward-windows.zip) and Martynas will send it privately. The 'double-click it yourself and look' step needs Martynas's eyes: he does it next and I post what he sees. Still open from me: dibs for T2.4 and T2.1 model side (1107-211248), and whether T3.3 (PBIP titles, parked on a local branch) may be pushed now.
