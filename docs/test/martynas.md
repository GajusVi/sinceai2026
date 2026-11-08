# Dashboard system test, part 2: Martynas's Claude (Sun 8 Nov, 02:40-03:05)

Iterations 3a-3c and 4a-4b of `docs/test/DASHBOARD_TEST_BRIEF.md`, plus the four majors Gajus found. Read-only: no repo file
changed except this report.

## How I ran it (read this first)
**I did NOT use a real browser.** The session has no browser tool (a tool search found none). So there are **no screenshots**, no
day/night *look*, and I did not open the .pbip in Power BI Desktop.

What I did instead is the closest thing available: I ran the real app script `frontend/steward_app.py` in Streamlit's own test
harness (`AppTest`), as **separate user sessions that share one data directory**. That is exactly the mechanism two browser
windows use (the inbox is a file in `STEWARD_DATA_DIR`; each window has its own `session_state`), so the cross-user checks are
real. I clicked the real buttons and read the real widgets and markdown. `make demo` equivalent: `STEWARD_USE_LLM=off`,
`STEWARD_CATALOG=datapack`, data dir copied from `demo/steward_seed`. **Live LLM: not tested** (no key on this machine).
AI calls: 0 (LLM off). Time to dashboard: not measured (the harness does not give a trustworthy browser time).
Scripts: `scratchpad/explore_ui.py`, `iter2.py`, `iter3.py` (not committed).

**Needs a person with a browser (about 5 minutes):** see "Not covered" at the end.

## Iteration table
| # | Who | Request | Verdict | Archetype | Visuals | Issues | Result |
|---|---|---|---|---|---|---|---|
| 3a | Worker22 -> Builder12 | "Line downtime" (button; not governed) -> "Ask the BI team for it" | n/a (request) | n/a | n/a | none | **Works.** Worker sees "Sent to the BI team". A *separate* builder session shows "Requests from the floor (1): line downtime for Worker22 (Equipment Ops, Plant-A). No report they can open has it yet" with **Start it / Decline**. Start it opens an interview on "line downtime for Plant-A". Worker22's next page load: "Your request "line downtime" was picked up: the BI team is building it (Builder12 (builder))." |
| 3b | Manager07 -> Builder12 | "How is Plant-B doing?" -> Use recommended -> "Send to the BI team for approval" | CREATE | OVERVIEW | kpi_strip + 2 bullets + 3 lines + stacked_100 + table | see M-A, m-A | **Works.** Builder session: "Waiting for your approval (1) ... from Manager07 (management), Plant-B", **Review** -> owner field -> **Create the report**. Journal line: actor `Builder12 (builder), requested by Manager07 (management)`, verdict CREATE, action approved, **spec_hash b205b94cbb4bb804**, lint `10 pass, 0 warn, 0 block`, `layout_source: overview`, `created_artifact_id` set. Manager's next load: "Your request ... was approved by Builder12 (builder). New artifact: ..." |
| 3c | Manager07 | same OVERVIEW; change Market / Product / Months | CREATE | OVERVIEW | 7 tiles each time | none | **Filters follow, nothing breaks.** OTIF tile: all 78.3% BREACH; Germany 80.1% BREACH; China 84.9%; Beyonttra 80.5% BREACH (inventory flips OK -> WATCH -> BREACH); months Jan-Jun: OTIF 82.9%, units 1,559,507. No exception, no "n/a". |
| 4a | see "Majors" | adversarial | see below | | | | |
| 4b | Manager07 | same OVERVIEW, "Day theme" toggle on and off | CREATE | OVERVIEW | 7 tiles | none | Toggling day/night does not crash or change any value (7 tiles, same numbers). **Look not judged (no browser).** |
| 4b | (export) | the approved 3b spec -> .pbip | n/a | OVERVIEW | 8 spec visuals -> 11 exported (strip -> 4 cards) | M-B | Exports (32 files, `cardVisual`, `clusteredBarChart`, `lineChart`, `tableEx`), bullets and stacked_100 listed in the README as drawn as clustered bars. **Does not use the 12-column grid** (page height 1750). Not opened in Desktop. |

## Blockers
**None found** in what I could run: no wrong number, no crash, no cross-plant leak in the paths I touched, the 3a/3b handoffs
work across sessions, and filters change the numbers correctly. (Plant-leak and role refusals were covered by Gajus; I did not repeat them.)

## Majors
**M-A. The approved OVERVIEW loses its layout identity (3b).** The stored spec `specs/b205b94cbb4bb804.json` has
`archetype: null` and every visual `span: null, row: null` (the kpi_strip, bullets and stacked_100 are kept as *types*). Only
`provenance.layout_source = "overview"` and the journal line's `layout_source: overview` record that it was an OVERVIEW. This is
the "known gap until spec.py gets the fields". Consequence: the approved spec re-renders from its types, and its .pbip does not get the grid (M-B).
Repro: Manager07 "How is Plant-B doing?" -> Use recommended -> Send; Builder12 Review -> owner -> Create the report; read `<data dir>/specs/<hash>.json`.

**M-B. An approved OVERVIEW exports as the old flow layout, not the grid.** Same spec exported with `pbip.export_pbip`: 11 visuals,
page height 1750, because no visual has `span`/`row`. My grid code (4b45a43) works (verified in Desktop earlier on a hand-built spec) but is
only triggered by those fields, so it is dormant for real specs until Donatas's spec.py fields land and specbuild fills them.
Fix: after the spec.py commit, make specbuild set `span`/`row` for OVERVIEW, then re-export and reopen in Desktop (I can do the PBIP side, 10 minutes).

**M-C (Gajus M2, confirmed through the UI). Time words are ignored and nothing says so.** "How is Plant-B doing in 2019?" ->
interview "Yes, use these" -> a normal Jan-Oct 2026 OVERVIEW. No caption or tile mentions a period (my check for "Jan", "Oct", "period", "latest month",
"2019" in the page text found none). Repro: Manager07, that sentence.

**M-D (Gajus M3, confirmed and worse). "Sales and supply" builds a dashboard titled "whether supply is safe" with ONE sales tile.**
Manager07 "How is the company doing overall, sales and supply?" -> scope question (All medicines) -> region question (Worldwide) -> Use recommended ->
title **"Bayer Pharma: whether supply is safe"**, one tile: **Net Sales EUR 17,339.6 M (-1.0% vs forecast)**, verdict CREATE "Nothing in the catalog answers this",
and the Why line says "Only reports that must not be the answer carry these metrics: AST-0335 (recommended for retirement)". The supply half of the
question vanished, and the title contradicts the content. The "Send to the BI team" button is enabled. Note: this is a *manager* seeing company-wide sales
(known and accepted, Gajus m5).

## Minors / checks of Gajus's list
- **M1 ("Show me Eylea in Japan, but not Japan, worldwide"): the "wall of n/a" did not reproduce through the UI.** Builder in expert mode -> **CLARIFY** (no cards).
  Manager through the interview -> the first screen asks "what is this about?" (How well a site is running / Whether supply is safe / How the business is doing).
  So the UI is safer than the script path Gajus used. I did not follow the interview to the end with defaults. The contradiction itself is still never named.
- **M4 ("plant b, otif, inventory and patient adherence"): partly explained.** The interview says "To judge how well a site is running I'd show on-time in-full and
  inventory coverage. (Equipment effectiveness (OEE), batch yield, downtime and cost per unit aren't measured...)". That is a generic list: **"patient adherence" is not named**.
  After Use recommended: tiles OTIF and Inventory; no gap tile for adherence.
- **m-A. Free-text owner is accepted.** In 3b I typed "Mika Virtanen" into "Report owner"; any string is accepted (Donatas already plans a pick-list).
- **m-B. The new artifact id is long and ends in a dash:** `new-on-time-in-full-inventory-coverage-demand-forecast-accuracy-units-`.
- **m-C. Tile delta text (Gajus V4 reproduced from the tile text):** "-0.0 vs last month" (inventory), "+332,608.0 vs last month" (units, a decimal on a count),
  "-4.1 vs last month" with no unit (OTIF, should be pp).
- **m-D. stacked_100 in Power BI is a plain clustered bar** (README says so). The "100% share" meaning is lost in the export. Power BI has a 100% stacked bar; I need a Desktop-saved example to map it (3 minutes of someone's time).
- **m-E. Months filter and tile periods:** with Jan-Jun selected the strip still says "vs last month" with no month named (Gajus m2).

## Suggestions, ranked
1. **Print the period on every OVERVIEW and say when the request's time words were not applied** (M-C, V3). S. Biggest chance of misleading a manager; same fix covers "2019" and "this quarter".
2. **When the asked-for KPI mix cannot be served, say what was left out and do not title the page for the half that survived** (M-D, M4). S/M. Add a gap tile or a one-line "not shown: supply KPIs / patient adherence".
3. **Close the OVERVIEW spec gap, then re-export** (M-A, M-B): spec.py fields -> specbuild fills span/row/archetype -> journal keeps them -> .pbip uses the grid. M (Donatas) + S (me, PBIP side + reopen in Desktop).
4. Owner pick-list, shorter artifact ids (m-A, m-B). S.
5. Unit-aware deltas (m-C). S.
6. 100% stacked bar template in the export (m-D). S/M, needs a Desktop-saved example.

## Verdict: OVERVIEW ships **ON** at 04:00
Reasons: every handoff I could run works across sessions (3a, 3b), the journal keeps who asked, who approved and the spec hash, the filters change the numbers
correctly (3c), day/night toggling is safe, the export builds, and nothing I ran produced a wrong number or a leak. The weak spots (period not shown, a half-served
question, the dormant grid in the export) fail the same way or more mildly than the old template, and the switch keeps old hashes. **Conditions I would set:** do suggestion 1 (period line) before the demo if there is time, and do not
show the .pbip of an *approved* OVERVIEW on stage until M-B is fixed and reopened in Desktop; show the hand-built overview export instead (it opened exactly as laid out).

## Not covered (needs a person with a browser, about 5 minutes)
1. Day and night **look** of one OVERVIEW (take one screenshot each): `make ui` or the .exe, Manager07 -> "How is Plant-B doing?" -> Use recommended -> "Day theme" toggle.
2. Two **real** browser windows (normal + private) on one `make ui`: the same flow as 3a/3b. My two-session test used the same shared file, so I expect it to behave the same.
3. Open `C:\SinceAI\pbip_overview_real\unzipped\*.pbip` (this approved OVERVIEW, flow layout) in Power BI Desktop and look at it.
4. Live LLM, phone width, the autofill dropdown (needs `streamlit-searchbox`, which is installed here; I did not exercise it), the receipts' AI-call count (LLM off = 0).
