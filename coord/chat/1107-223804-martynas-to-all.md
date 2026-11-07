id: 1107-223804-martynas-to-all
from: martynas
to: all
kind: done
created: 2026-11-07 22:38
re: 
---
WINDOWS .exe BUILT (Martynas): dist\BI Steward\BI Steward.exe (PyInstaller 6.22.3, pywebview 6.2.1 / WebView2, Windows 11), built with .\run.ps1 app-setup + tools\build_app.py with no changes to the repo. Self-test: run 1 FAIL (login page ok, workspace ok after 12.7 s, signed in ok, 'log out: False'), run 2 PASS (workspace after 4.8 s, log out ok). Cause = a RACE IN THE SELF-TEST, not the app: _selftest (app/main.py:181) treats the workspace as ready when 'Journal' appears, then clicks the Log out anchor at once, but Streamlit renders the sidebar anchor (a.bs-logout) slightly later; on a cold start the exe is slower (12.7 s) so the click found nothing. Proof: in a diagnostic run from source the first query found NO anchor (anchors: []), the same session a few seconds later had it (a.bs-logout href=login.html) and clicking it returned to login.html within 5 s. FIX for Gajus (app/main.py, your file): before the click add wait(lambda: js("!!document.querySelector('a.bs-logout')"), 60) and use document.querySelector('a.bs-logout').click(). Same on the Mac, it just passes there by speed. Also: dist\ is git-ignored (60 MB exe + _internal, about 0.5 GB) so teammates and the submission need the folder zipped and shared outside git; tell me where it should go. Login accounts as before. The packaged app runs with the LLM off (no .env).
