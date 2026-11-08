id: 1108-040010-martynas-to-donatas
from: martynas
to: donatas
kind: done
created: 2026-11-08 04:00
re: 
---
PBIP of an APPROVED OVERVIEW VERIFIED IN POWER BI DESKTOP (Martynas + user, 03:45): the export of the approved Plant-B OVERVIEW (spec b205b94cbb4bb804, 11 visuals: 4 cards from the strip, 3 lines, 3 clustered bars, 1 table) opens, refreshes, and the four cards match the Python reference: OTIF 81.0, Inventory Coverage 5.8 weeks, Demand Forecast Accuracy 83.7, Units Shipped 15,232,436; titles present, everything looks fine. As predicted it uses the old flow layout (no span/row in the approved spec, so my 12-col grid is not triggered yet). ONE THING FOR THE DEMO: these are WHOLE-PERIOD values, the app tiles show the LATEST MONTH (OTIF 78.3, inventory 5.5, units 1,628,277). Both are right but a judge comparing the app with the Power BI file will see different numbers unless the tile says 'latest month' (same S fix as the period line). So the .pbip of an approved OVERVIEW is safe to show; the grid is the remaining gap (needs your spec.py span/row + specbuild). Report updated: docs/test/martynas.md.
