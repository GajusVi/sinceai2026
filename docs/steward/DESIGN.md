# BI Steward design system (Sat 7 Nov, Gajus): "the ruling"

Every request ends in one governed decision. The screen reads like a calm, typeset ruling: one answer sentence, one
verdict, the few KPIs that matter, who signs off. Audience: a non-technical site head first, the BI team second.

Sources: design-taste-frontend (leads: house rules, copy, palette + type library), ui-ux-pro-max (lookup: chart choice,
contrast), design-motion-principles (Emil lens, create + audit). Streamlit = Taste's system, not its starter page.

- Colour: Taste palette `white-link-blue`: ground #FFFFFF, fill #F4F4F4, ink #111111, muted #6B6B6B, accent #1A4BE0
  (primary actions only). Verdict colours only on the verdict: REUSE #15803D, EXTEND #1A4BE0, CONSOLIDATE/MIGRATE
  #B45309, CREATE ink, RESCUE #B91C1C. All text colours >= 4.5:1 on ground and fill (checked).
- Type: Instrument Sans (Taste `library/type.json`, OFL), self-hosted in frontend/static/fonts so `make demo` runs
  offline. Tabular numerals on every figure. Record ids in system monospace.
- Look: flat fills only. No borders, outlines, shadows, gradients or emoji. Areas separate by whitespace and fill.
- Ask (novice): empty state = "What do you need to know?", input, three chips. Interview = one question at a time,
  "Question n of 5", answers as pills, "Use recommended" as a text button, own answers muted above. Result = headline,
  verdict strip, dashboard preview (3-5 tiles, <= 2 charts), Why (<= 3 sentences), approval (Approve primary, Send
  back secondary), "Show details for the BI team" toggle (AI trail, ids, lint, exports). Expert: same order, denser.
- Catalog health: three numbers from code (views < 1,000 in 30 days, non-canonical KPI use, missing/inactive owner),
  one sortable table. Journal: timeline, newest first. Catalog: search + table.
- Motion: new message 150 ms fade + 4px rise; verdict strip 200 ms fade after the headline; button press scale 0.97,
  hover 150 ms. Building state = still skeleton. Nothing under prefers-reduced-motion.
- Files: .streamlit/config.toml (theme, fonts), frontend/steward.css (all component CSS), frontend/ui.py (components).
- Known: chart colours are set in steward/render.py (Donatas), not by the theme.
