# Dashboard system test: brief for Gajus's and Margiris's Claudes (Sun 8 Nov, 02:15, Donatas as team lead)

**Goal.** Test the new dashboard system end to end with real users of every role, in several iterations, and come back
with evidence and ranked suggestions. Each iteration must **generate or request a different dashboard**: different
role, question, scope, archetype or verdict. This is a test, not a build: **read-only**. You write only your report
file. No code edits, no `make warm`, no commits outside `docs/test/`.

**Deadline: 03:30.** I decide at 04:00 whether OVERVIEW ships on or off (switch `STEWARD_OVERVIEW=off`), so blockers
found before 03:30 count most. Post `done` with your top 3 findings when your report is pushed.

## What is new (what you are testing)
- **OVERVIEW archetype** (fe0dd19): an overview question (interview theme `plant_efficiency`, `supply_health` or
  `business_performance`) asked by **management or builder** becomes a production-style dashboard:
  - a header band;
  - a KPI strip of up to 8 status tiles (ok / watch / breach only where a governed threshold exists);
  - 4-6 charts picked per KPI by rule: bullet vs target, trend + dashed forecast, diverging variance, 100% share of
    <= 5 parts;
  - one exceptions table.
  Everything else (workers, single-KPI questions, REQ-0001) keeps today's template.
- **Rendering** (4de1699, f2f165b): status tiles, the new chart types, the 12-column grid, day and night.
- **Lint** (4a80529): the strip counts as one visual, at most 6 charts, gaps only as tiles.
- **Power BI export** (4b45a43, Martynas): the grid maps to visual positions; the new chart types become clustered bars.
- Also on main: day/night toggle, tinted chips, receipts strip ("How this was decided"), autofill dropdown
  (needs `streamlit-searchbox==0.1.24`; without it, chips only).

## Setup
- `git pull --rebase`. Run `make ui` (live LLM, if your key works) or `make demo` (LLM off, deterministic). The desktop
  app (`make app`) is fine on a Mac.
- Accounts:
  - Worker21 / Worker123 (Plant-A, Warehouse Ops)
  - Worker22 / Worker123 (Plant-A, Equipment Ops)
  - Manager07 / Manage123 (Plant-B)
  - Builder12 / Admin123 (BI team, whole company)
- **Different users at the same time:** open two browser windows (one normal, one private), or two `make ui` ports
  (`--server.port 8502`), and log in as two roles at once. The request inbox is shared through the data dir, so a
  request sent by one user must appear for a builder in the other window.

## Iterations (each one a different dashboard; record every one)

| # | Who | Request | Expect |
|---|---|---|---|
| 1a | Manager07 | How is Plant-B doing? | OVERVIEW: band, 4 tiles (OTIF BREACH), 6 charts, OTIF exceptions table |
| 1b | Builder12 | How are we doing in LATAM this quarter? | OVERVIEW, smaller (LATAM has 2 countries: by-country charts drop) |
| 1c | Manager07 | Is supply safe for Plant-B? | OVERVIEW (supply_health) |
| 1d | Worker21 | the same Plant question via the floor buttons / chat | worker template, reuse only, never OVERVIEW |
| 2a | Builder12 | Xarelto net sales in Germany | REUSE AST-0191, today's template (must not change) |
| 2b | Builder12 | REQ-0001 (Nubeqa global) | template, unchanged |
| 2c | Manager07 | How efficiently is this plant running? | "this plant" = login plant (Plant-B), OVERVIEW |
| 2d | Manager07 | a question about Plant-A | refused or routed: other plant |
| 3a | Worker22 -> Builder12 | worker requests a missing number; builder sees it in the other window, starts it | cross-user handoff works; dashboard built with the requester attached |
| 3b | Manager07 -> Builder12 | manager sends an OVERVIEW to the BI team; builder approves it with an owner | journal line, spec hash; check whether the approved spec keeps the grid (known gap until spec.py gets the fields) |
| 3c | Builder12 | change product / market / months on an OVERVIEW | tiles, charts and table follow the filters; nothing breaks |
| 4a | any | an ambiguous, contradictory or out-of-scope request ("Show me Eylea in Japan, but not Japan, worldwide"; a KPI with no data) | CLARIFY / NOT_FEASIBLE / gap tiles, never invented numbers |
| 4b | any | the same OVERVIEW in day and in night; export the .pbip of one OVERVIEW | readable in both themes; export downloads |

Add 2-3 requests of your own that you think will break it.

## What to record per iteration
- user + role
- exact request text
- verdict
- archetype (OVERVIEW or template)
- visual list (types + rows)
- lint result (non-pass rules)
- time to dashboard
- AI calls (if visible in the receipts)
- issues, each with a severity:
  - **BLOCKER:** wrong number, crash, data leak across plants, wrong verdict;
  - **MAJOR:** misleading or unreadable;
  - **MINOR:** polish.
- a screenshot path (your scratchpad)

## Report: `docs/test/<your name>.md`
1. The iteration table above, filled in.
2. **Blockers first**, each with a repro.
3. **Suggestions, ranked**: what to change in the dashboard system, with expected effect and effort (S/M/L).
4. Your verdict: **OVERVIEW ships on or off at 04:00**, and why.

## Split
- **Gajus's Claude:** iterations 1a-1d, 2a-2d (roles and scope), plus your own break attempts on the interview path.
- **Margiris's Claude:** iterations 3a-3c, 4a-4b (cross-user handoffs, governance, adversarial), plus a lint and
  verdict check: are the 73 labelled cases still green (`make eval`, do not commit results.json unless you normally do)?
- If one of you cannot run, the other takes all iterations and marks the gap.

Questions or blockers: `tools/coord.py say donatas "..." --kind question`.
