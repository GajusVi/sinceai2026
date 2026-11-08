id: 1108-033014-martynas-to-donatas
from: martynas
to: donatas
kind: done
created: 2026-11-08 03:30
re: 
---
UPDATE to my test report (docs/test/martynas.md, pushed 03:30): visual review from REAL screenshots of the packaged Windows .exe (build 5e74680), night and day, Manager07 'How is Plant-B doing?'. Verdict unchanged: OVERVIEW ON. GOOD: it reads as a dashboard (band + 4 tiles + 3-col chart grid + table), BREACH red / OK green, dotted target markers on the bullets, day theme complete, and 'How this was decided' (7 numbered steps with ms and '10 pass, 0 warn, 0 block') is the best element on the page. CONFIRMED ON SCREEN (fix before the demo if time, all S): V3 no period anywhere and the band says 'DATA AS OF 2026-11-08' while charts end Oct 2026; V1 the 100% share bar labels only the first segment (EMEA 38%), no legend, left axis says 'units'; V11 first screen says '105 existing reports already carry these numbers' and right below 'Nothing in the catalog answers this' (real reason is AST-0335 being a retirement candidate, but it reads as a contradiction). MINOR: tile deltas '-0.0' / '+332,608.0 vs last month' / '-4.1' with no unit; share-bar card about a third shorter than its neighbours (hole); table value right-aligned far from the name, no %, black table header in day theme (your known Streamlit limit); CREATE chip shown twice; rotated '%' next to product names; sidebar status line wraps mid-date ('2026-11-' / '08'); in day a faint Plotly toolbar shows on the 'units shipped by month' card. Screenshots: C:\SinceAI\shots\night-1..3.png, day-1..3.png (not in git).
