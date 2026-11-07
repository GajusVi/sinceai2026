id: 1107-212146-donatas-to-gajus
from: donatas
to: gajus
kind: done
created: 2026-11-07 21:21
re: 
---
Login window design pushed (c6d6301): app/shell/login.html (+ OWNERS: frontend/steward.css, frontend/ui.py, app/shell/ -> donatas). Contract as in my 21:19 message: ids #user #pass #signin #error #loading; api.login(user, pass) -> {ok, error?}; then I poll api.ready() every 300 ms and call api.open(). Please open it at 960x600 (it falls back to a single column below 720 px, so 440x600 also works). Open it in a browser to see the mock flow. Next I style the rail/top bar (.st-key-bs-rail, .st-key-bs-topbar) once your skeleton commit is on main: post the id.
