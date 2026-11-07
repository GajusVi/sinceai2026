id: 1107-234218-donatas-to-all
from: donatas
to: all
kind: done
created: 2026-11-07 23:42
re: 
---
DONE (Donatas): day/night theme + centred layout. Login: bigger logo, no subtitle, centred group, sun/moon toggle (localStorage), globe stays dark (02ccdb3, 3329617). App: 'Day theme' toggle at the sidebar bottom; all ui.py colours are CSS variables (use ui.GOOD/BAD/... or var(--ink) etc., never hex) (3329617). render(..., theme='day') recolours charts, night unchanged (3329617). Layout: 1100 px centred column, start page with the input centred + chips, 36/40 px controls (4230ca1). Open: Gajus ask 1107-233304 (sidebar examples out, 4th chip 'Net sales for Eylea in Japan', theme=ui.theme() into render, set_theme in app/main.py). Known limit: st.dataframe stays dark in day (Streamlit canvas).
