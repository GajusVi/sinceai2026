id: 1107-215427-donatas-to-gajus
from: donatas
to: gajus
kind: done
created: 2026-11-07 21:54
re: 
---
FYI (4988c74): login right panel redesigned (user brief): one large lit globe, no console. app/shell/vendor/cobe.js is REMOVED (only cobe's land mask is used, inlined in login.html), so the build needs only app/shell/login.html + THIRD_PARTY_NOTICES.md + frontend/static/fonts. Page no longer uses ES modules: works from file:// too. Left half, ids and api contract unchanged.
