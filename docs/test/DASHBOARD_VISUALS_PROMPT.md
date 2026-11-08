# Prompt: make the rendered dashboards clean and readable (on main)

Written by Margiris's Claude, Sun 8 Nov. For Donatas (owner of steward/render.py and frontend/ui.py), or a
session he OKs with a TEMP OWNERS line. Paste everything below the line into a fresh Claude Code session.

---

# Task: make the rendered dashboards clean and readable

## Context
Repo: SinceAI2026 (BI Steward). Read CLAUDE.md and NOTES.md first. `git pull --rebase --autostash` before editing.
The dashboards are drawn by `steward/render.py` (Plotly figures, `_layout`, `TEMPLATES` day/night)
and placed on the page by `frontend/ui.py` (`header_band`, `tiles`, `card_row`, `overview`, `kpi_card`).
The numbers are right. The problem is how the dashboards look: they are cluttered and inconsistent.
The findings are in docs/test/gajus.md, "Visual issues" V1-V11. Read that section in full.

## Rules
- Work on main, small commits, `make test` green before every push. Never force-push, never --no-verify.
- render.py and ui.py belong to Donatas (OWNERS). If you are not Donatas's session and the pre-commit hook
  refuses a commit, stop and ask him via `tools/coord.py ask donatas ...`.
- Freeze is 05:00. Do the items in the order below and stop at the freeze; list what is left.
- Do not change numbers, verdicts, lint rules, spec hashes or `steward/models.py` / `spec.py`.
  This is display only. If a fix needs a spec field, write it down as a request and skip it.
- Only Plotly + the existing ui.py tokens. No new libraries, no React/Tailwind/shadcn, no custom CSS
  beyond what ui.py already injects.

## Design rules (apply them through ui.py tokens and render.py `_layout`, in one place, not per chart)
1. One design system: every chart gets its fonts, axis style, gridlines, margins and colours from
   `_layout` + TEMPLATES. Every card goes through `ui.kpi_card` / `card_row`. Remove one-off styling.
2. Layout shell first: header band -> KPI strip (max 4 tiles per row) -> chart grid -> full-width table.
   Every card in a grid row has the same height. A lone last card spans the full row, with no gap left beside it.
3. Colour: muted neutral surfaces, ONE accent colour for the data, red/green only for BREACH/OK status.
   Text colours come from the existing tokens. Both day and night themes must pass.
4. Do not add: heavy shadows, neon colours, a badge on every item, cramped padding, the same title
   repeated, rotated axis titles that only repeat the unit, or a legend when direct labels would do.
5. Hierarchy: the eye lands on the KPI tiles first, then the trends, then the detail table.

## Fix list (in priority order, one commit per item)
1. V1 share bar (stacked_100): every segment labelled or a legend, axis is "% of total", not "units".
2. V2 growth line: a fraction axis shown as a percent (tickformat), matching the tile (11.9%, not 0.2).
3. V4 tile deltas: unit-aware ("pp" for rates, no decimals on counts, no "-0.0").
4. V5 ragged last row (see design rule 2).
5. V6 the title said 3 times: one page title, one verdict chip.
6. V7 table: value column next to its label, units on values, header follows the day theme.
7. V8 axis titles: one size, one rule (unit in the hover/tick format, not a rotated title).
8. V9 the day theme with the sidebar open clips the last tick/point: fix margins/autorange.
9. V10 the sidebar "»" button overlaps the title, and the status line is cut off.
Skip V3 (period/date, its own fix) and V11 (wording, other owners). List them under "Not done".

## Method
- Load the `dataviz` skill before you touch any chart code.
- Before any change, take screenshots with `make demo`: Manager07 "How is Plant-B doing?" (Use recommended)
  and Builder12 "LATAM this quarter", night + day, desktop + 390 px
  (docs/test/BACKTEST_FEEDBACK.md says how to set the width). Save them to the scratchpad as
  `<case>-<theme>-<width>-before.jpg`.
- Fix one chart type or component at a time. After each fix, take the same shots again (`-after.jpg`).

## Done means
- Each item fixed or listed with a reason. `make test` and `make lint` green.
- A NOTES.md line + `tools/coord.py say all "..." --kind done`: each V-item -> commit id, what is not done.
- No spec hash changed: re-render the 3b spec (`specs/b205b94cbb4bb804.json`) and check its hash.
- If the demo cache depends on the figures, tell Donatas to re-run `make warm` (only he runs it).
