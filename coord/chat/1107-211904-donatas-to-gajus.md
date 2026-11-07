id: 1107-211904-donatas-to-gajus
from: donatas
to: gajus
kind: need
created: 2026-11-07 21:19
re: 
---
T2.6 login (Donatas): I write app/shell/login.html myself now, so you can skip the skeleton and only wire the API. Design = split screen: left compact login, right dark panel (rotating dot globe on canvas, slow colour glow, faint grid, console that types the BI Steward chain). Fully self-contained, no CDN, offline. Requests: (1) login window 960x600 (split screen does not fit 440 wide; below 720 px wide the right panel hides, so 440 still works). (2) Contract I code against, tell me if yours differs: ids #user #pass #signin #error #loading; JS: const r = await window.pywebview.api.login(user, pass) -> {ok: bool, error?: str}; on ok I show #loading and poll await window.pywebview.api.ready() -> bool every 300 ms, then call window.pywebview.api.open(). Without pywebview (opened in a browser) the page runs a mock so I can design it. (3) Fonts: I reference ../../frontend/static/fonts/ by relative path; for the PyInstaller bundle please keep that relative layout or tell me the path.
