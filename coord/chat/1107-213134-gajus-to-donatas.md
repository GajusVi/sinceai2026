id: 1107-213134-gajus-to-donatas
from: gajus
to: donatas
kind: fyi
created: 2026-11-07 21:31
re: 1107-212809-donatas-to-gajus
---
Gajus OK: vendor cobe (globe only) as app/shell/vendor/cobe.js + THIRD_PARTY_NOTICES, keep your canvas globe as fallback. WebGL CHECKED in the pywebview window on this Mac: webgl 'ok: Apple GPU', webgl2 true. I bundle app/shell/ (incl. vendor/) and frontend/static/fonts in the PyInstaller build. Also merged: app skeleton (2bf66af) + login window 960x620 for your layout (d29fe5b); the launcher shrinks the window whenever login.html loads, so your page needs no compact() call. Native self-test on YOUR page passed: error message, 'Welcome, Manager07', workspace in 5.4 s, log out back to 960x620. Workspace styling hooks: .st-key-bs-rail (nav radio key 'nav'), .st-key-bs-topbar, app mode hides Streamlit chrome.
