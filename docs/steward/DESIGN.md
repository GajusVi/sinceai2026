# BI Steward design system (Sat 7 Nov, 22:45, Donatas): dark, dense, one surface

**Why dark (changed from the light "ruling" design of Sat morning).** The desktop app opens on a dark login window with
a lit globe of the data pack's markets. A stark white workspace after it read as two products. The app is now one dark,
dense surface, in the spirit of analyst tools (Palantir / Anduril; shadcn/ui dark zinc, Tremor KPI cards and Blueprint
density as visual reference only: no React, npm, CDN or new Python package). Dark also suits the audience: long
sessions, dense tables, numbers first.

**One source of truth.** Tokens live in three places that must change together: `frontend/ui.py` (Python constants),
`frontend/steward.css` (CSS variables) and `.streamlit/config.toml` (Streamlit theme). Charts take the same values in
`steward/render.py`. The login window (`app/shell/login.html`) uses the same tokens.

| Token | Value | Use |
|---|---|---|
| ground | #09090B | page background (zinc-950) |
| panel | #111114 | every content block: cards, verdict, chat, tables, charts, sidebar |
| raised | #18181B | inputs, active nav row, pills |
| line | #27272A | 1 px borders and chart gridlines |
| ink | #FAFAFA | text (18:1 on panel) |
| muted | #A1A1AA | secondary text, labels, axis text (7.4:1) |
| faint | #71717A | decoration only (3.9:1: never body text) |
| accent | #1A4BE0 | primary buttons (white text) |
| focus | #3B6BFF | focus ring (1 px border + 3 px glow), active nav edge, chart "actual" (4.25:1: graphics, not text) |
| accent text | #6B8CFF | links and accent-coloured text (6.1:1) |

**Verdict colours** (only on the verdict; contrast on the panel #111114): REUSE #4ADE80 (10.8), EXTEND #6B8CFF (6.1),
CONSOLIDATE / MIGRATE #FBBF24 (11.3), RESCUE #F87171 (6.8), CLARIFY / NOT_FEASIBLE #A1A1AA (7.4), CREATE #FAFAFA (18).

**Type.** Instrument Sans for UI text (self-hosted, OFL). Geist Mono 1.9.2 (Vercel, OFL, self-hosted in
`frontend/static/fonts`) for numbers, KPI values, ids, spec hashes and small uppercase labels. Base 14 px; the dashboard
headline is 26 px, section headings smaller. Tabular numerals on every figure.

**Components.**
- Sidebar: panel with a 1 px right edge; the nav rail is a list of rows (no radio dots), the active row raised with a
  focus-blue left edge; mono uppercase section labels; the user block a compact card.
- Top bar: page name, then user / role / plant / AI status in small mono caps, a 1 px rule under it.
- Interview: one bordered panel, one row per turn, mono speaker label (YOU / STEWARD), "Question n of 5" in mono.
- Verdict banner: panel, 3 px left edge in the verdict colour, the verdict word as a mono outlined badge.
- KPI cards (Tremor-like): panel, mono uppercase label, large mono value, delta with an arrow (sign of the delta) in
  green or red when render.py marks it good or bad, grey when neutral (a falling number is not always bad). Cards sit
  side by side in a grid.
- Charts: transparent background on a panel, #27272A grid, #A1A1AA mono tick labels, actual in #3B6BFF, forecast
  dashed grey. Deterministic: fixed values, the same spec gives the same figure. The .pbip export is not touched.
- Density: tighter vertical rhythm (block gap 0.55 rem, roughly half of before); content in bordered panels, not
  floating on the page.

**Motion.** New message 150 ms fade + 4 px rise; verdict 200 ms fade; button press scale 0.97. Nothing under
prefers-reduced-motion.

**Files.** `.streamlit/config.toml` (theme, fonts), `frontend/steward.css` (all component CSS), `frontend/ui.py`
(components + tokens), `steward/render.py` (chart tokens), `app/shell/login.html` (login window).
