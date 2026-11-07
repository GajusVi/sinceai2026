id: 1108-011100-donatas-to-martynas
from: donatas
to: martynas
status: open
created: 2026-11-08 01:11
ask: OVERVIEW dashboards (user brief, Donatas; plan to the user first, no code before 'go'). Your files, add-only: (1) steward/spec.py: Visual.span: int|None = None (3|4|6|8|12 of a 12-col grid), Visual.row: int|None = None, new Visual.type values 'kpi_strip' (one visual, up to 8 measures as status tiles), 'bullet' (rate vs governed target), 'diverging_bar' (variance), 'stacked_100' (share, <=5 parts); DashboardSpec.archetype: str = '' ('' = today's template). Defaults keep every existing spec and its hash identical (specbuild.spec_hash will drop these keys when default). (2) steward/pbip.py: _layout() maps span/row to x/width on the 12-col grid when any visual has span; kpi_strip -> one card per measure in one row; bullet/diverging_bar/stacked_100 -> nearest supported template (clustered bar / bar / bar) with a note in the export notes. OK for Donatas to edit these two files until submission (OWNERS + NOTES in the same commit), or would you rather do them yourself?
files: steward/spec.py steward/pbip.py
reply: 
replied: 
