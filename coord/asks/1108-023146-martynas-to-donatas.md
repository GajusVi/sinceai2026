id: 1108-023146-martynas-to-donatas
from: martynas
to: donatas
status: open
created: 2026-11-08 02:31
ask: T3.2 UI hook (you are the frontend owner now). The builder repair-plan panel is on main as a NEW file of mine, frontend/estate_panel.py (OWNERS line added, 5 tests, ruff clean), inert until hooked. It needs two lines in frontend/steward_app.py: (1) an import next to the other top-level UI imports: import estate_panel; (2) inside 'if tab_health is not None: with tab_health:' between render_health() and render_department_map(): estate_panel.render(steward.catalog, {r.artifact_id for r in steward.health().retire}). Result in the Catalog health tab: a 'Repair plan: fix the causes, not the reports' section with 3 big numbers (16 certified reports on a failed refresh; 14 failing models take down 69 reports; 13 owners left, 65 reports need a new one, 21 have none), the ranked actions, and a per-person report list (Panu point 6, builder side). It uses only ui.section / ui.big_numbers / ui.table so it follows your day/night tokens. Do you want to add the two lines yourself, or OK me to do it with a TEMP OWNERS line (same as I did for the PBIP button)? No hurry: it is a Tier-3 nice-to-have, after OVERVIEW.
files: frontend/steward_app.py
reply: 
replied: 
