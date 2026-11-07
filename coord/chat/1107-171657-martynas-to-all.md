id: 1107-171657-martynas-to-all
from: martynas
to: all
kind: done
created: 2026-11-07 17:16
re: 
---
Layout data side done (c28331a). For Margiris' layout.py: semantic.profile(spec.measures, frames, spec.filters) -> {measure name: MeasureProfile(months, members{dim:n}, null_share, dq, forms, bar_dimensions)}; semantic.check_visual(profiles, type, measures, dimension) -> list of problems (empty = legal): a gap only as 'gap', trend needs >= 6 months, bar needs a dimension with 3..20 members. Thresholds in steward/config.py LAYOUT_*. pbip.py now orders and positions visuals by Visual.step (unset last; no steps = old layout). Donatas: same order in render.py. Missing: visual titles from Visual.question (need a Desktop-saved title).
