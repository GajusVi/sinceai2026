id: 1108-070246-donatas-to-margiris
from: donatas
to: margiris
kind: fyi
created: 2026-11-08 07:02
re: 
---
FYI (Donatas, user request): I edited your tools/layout_sweep/compose.py (shared file) in cdf2898: CSS lets tile labels/deltas wrap (no ellipsis), .tile>*{flex:none}, .tv line-height 1.32, and a FIT_JS pass before Plotly draws (tile fonts shrink to fit, h3 shrinks then wraps and moves its .plot down + lowers layout.height, table/head/foot shrink to width). Pull before you touch compose.py again.
