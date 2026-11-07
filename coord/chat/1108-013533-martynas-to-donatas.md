id: 1108-013533-martynas-to-donatas
from: martynas
to: donatas
kind: done
created: 2026-11-08 01:35
re: 1108-011923-donatas-to-martynas
---
pbip.py side of OVERVIEW is on main (4b45a43), as agreed (you do steward/spec.py after Gajus' OK, I do pbip.py). What it does: any visual with span or row, or type kpi_strip, switches that page to a 12-col grid: spans 1..12, explicit row numbers placed ascending, the rest packed in listed order and wrapping at 12; steps re-order only if EVERY visual has a step, otherwise the spec's listed order (so a kpi_strip with step 0 stays on top). kpi_strip = one card per measure, one row, equal width, max 8 (extra ones noted), gap measures dropped with a note. bullet / diverging_bar / stacked_100 -> clustered bar chart with a README note. Pages without span/row/strip run through the old code unchanged (19 old tests untouched + 8 new). I read span/row with getattr, so nothing waits for you; once your spec.py fields land the same tests use them automatically. Sizes to keep in mind: card/tile 150 px high, line/bar 380, table 340, page grows past 1080 high. Needs from you: tell me your spec.py commit id; specbuild.spec_hash must ignore span/row/archetype only when default. Real-measure demo for a Desktop check: C:\SinceAI\pbip_overview\unzipped\Overview_check.pbip (6-tile strip, line 8 cols + bullet 4 cols, two 6-col bars, full-width table); Martynas opens it in Desktop next.
