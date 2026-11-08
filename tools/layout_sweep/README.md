# layout_sweep: weighted 16:9 dashboards + the 100-variant sweep

Why: the app's OVERVIEW grid is symmetric by construction (`specbuild._overview_page`: `12 // len(row_charts)` spans, every chart
`height=300`), and no prompt touches that. This folder holds the fix as standalone code (new files only, nothing owned by
anyone else is edited) and a sweep that renders N variants from the real pipeline.

- `presets.py`  layout trees (row/col with weights; leaves chart/kpi/table). 11 presets by role + the `baseline_equal` reference.
- `compose.py`  RenderedDashboard -> 1920x1080 page (CSS-positioned, Plotly). Biggest slot gets the most important chart;
                empty slots are pruned; a preset with too few chart slots splits its smallest readable slot (never drops a chart).
- `sweep.py`    `python tools/layout_sweep/sweep.py --n 100 --out out/layout_sweep`
                 -> png/ (one per variant), sheet_<role>_N.png, before_after_N.png, gallery.html, results.csv/json, summary.md

Knobs the sweep varies: role (worker 20 / management 40 / builder 40), preset, hero ratio .56-.72, KPI band height, mirror, gap, theme.
Content (numbers, verdicts, footer) is the app's own: Steward.build + render.render with the LLM off.

Needs: `pip install plotly pandas pydantic openpyxl rapidfuzz scikit-learn playwright pillow` and `playwright install chromium`.
Score (0-100) is a heuristic: unequal chart areas, hero holds ~40% of chart area, readable cells (>=330x190), hero reads first,
KPI first, nothing clipped. It is not a judgement of taste: compare against the Bayer ground-floor example by eye.

Wiring into the app later (Donatas): `compose.build(dash, preset, params, role, theme, meta)` returns (html, metrics);
`st.components.v1.html(html, height=1080, scrolling=False)` in `ui.overview`. A real fix in `specbuild._overview_page`
would pick weights instead of `12 // n` and needs an optional weight/height on `spec.Visual` (ask Donatas).
