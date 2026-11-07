id: 1108-000607-donatas-to-gajus
from: donatas
to: gajus
status: open
created: 2026-11-08 00:06
ask: Day/night completion (user brief, Donatas). Two mechanical edits in frontend/steward_app.py, no logic change: (1) every st.dataframe( call (9 today: l.466, 723, 740, 1003, 1178, 1221, 1244, 1273, 1319) -> ui.table( with the same arguments (frontend/ui.table wraps st.dataframe with a per-theme pandas Styler; lists of dicts are fine, column_config/height/hide_index pass through; sorting, search, download keep working). (2) l.419 plotly_chart(fig, use_container_width=True, key=...) -> add theme=None (so Streamlit does not override our day/night Plotly templates; render() already builds per theme, 7a40574). ui.table is on main in the next minutes.
files: frontend/steward_app.py
reply: 
replied: 
