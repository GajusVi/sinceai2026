id: 1107-221450-gajus-to-martynas
from: gajus
to: martynas
kind: need
created: 2026-11-07 22:14
re: 
---
WINDOWS APP BUILD (Gajus, T2.6): you build, Margiris verifies. Steps: git pull; .\run.ps1 app-setup; .\run.ps1 app-build -> dist\BI Steward\BI Steward.exe, and build\selftest.txt must say RESULT: PASS (it logs in as Manager07, opens the workspace, logs out, in the real window). Then double-click the .exe once yourself and look at it. Post: PASS/FAIL, build time, folder size, and any error lines; I fix packaging problems from your log. Notes: pywebview uses WebView2 on Windows (preinstalled on Win10/11); the .exe has no .env, so the LLM is off (rules + demo cache). If PyInstaller misses a module, paste the 'No module named' line. Your Desktop check of the live PBIP can use the same machine.
