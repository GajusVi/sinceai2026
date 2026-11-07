id: 1107-212809-donatas-to-gajus
from: donatas
to: gajus
kind: question
created: 2026-11-07 21:28
re: 
---
Login window (c6d6301), FYI + question. The effects in app/shell/login.html are hand-made (canvas dot globe, CSS glow, CSS grid, JS typewriter): the brief said 'libraries as visual reference only, rebuild the effect', so no repo code was used. Option now: use the real libraries, offline. (1) Globe: vendor the real cobe (github.com/shuding/cobe, MIT; the library Magic UI's Globe uses) as app/shell/vendor/cobe.js, loaded by relative <script src>, configured like Magic UI's globe. (2) Port Magic UI Flickering Grid + Animated Terminal from their source to plain JS, Aceternity Aurora only if its source is public; licence notices kept + THIRD_PARTY_NOTICES. Plan: globe only (the one visible gain), the rest stays as is. Questions for you: OK to vendor cobe? Your PyInstaller build then must bundle app/shell/vendor/ (and app/shell/ fonts path ../../frontend/static/fonts/). cobe is WebGL: please confirm pywebview's WebKit window renders WebGL on the Mac build (if not, the current canvas globe stays as fallback, I keep both).
