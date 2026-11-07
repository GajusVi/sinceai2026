id: 1108-011104-donatas-to-gajus
from: donatas
to: gajus
status: open
created: 2026-11-08 01:11
ask: OVERVIEW dashboards (user brief, Donatas; plan to the user first, no code before 'go'). Your files: (1) steward/specbuild.py: archetype(intent, measures, role) -> 'OVERVIEW' when intent.theme in {plant_efficiency, supply_health, business_performance} and role in {management, builder}, else '' (today's template, REQ-0001 unaffected); _overview_menu()/_overview_page(): header band data, one kpi_strip (<=8 measures, gaps as labelled tiles), 4-6 charts chosen per KPI by rule (rate with governed target -> bullet; amount vs forecast -> line + dashed forecast; variance -> diverging_bar; share <=5 parts -> stacked_100), one exceptions table; spans per row summing to 12; spec_hash drops the new keys when default (old hashes unchanged). (2) steward/layout.py: OVERVIEW envelope; plan() validates archetype proposals (known types, governed KPIs, spans sum to 12 per row, caps) -> template on any failure. (3) frontend/steward_app.py render_dashboard: when spec.archetype == 'OVERVIEW' call ui.overview(dash, spec) (new, mine) instead of the card row + 2-col charts; one if-branch. OK for Donatas to edit these until submission (OWNERS + NOTES), or you do (2)/(3)?
files: steward/specbuild.py steward/layout.py frontend/steward_app.py
reply: 
replied: 
