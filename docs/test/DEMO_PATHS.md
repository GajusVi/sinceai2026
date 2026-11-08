# Demo readiness: fixes to make, and the path to take for each role (Gajus's Claude, Sun 8 Nov ~03:30)
Sources: docs/test/gajus.md (pipeline + screen), docs/test/martynas.md, BUILD_PLAN section 8 (demo story).
How checked: each path below was run through the app's code path (LLM off, `docs/test/backtest1/run_iter.py`); 1a and 1b were also
seen in Chrome. Anything marked UNSEEN has not been looked at on screen. Re-run each path once on the final build before recording.

## A. Fix before recording (one merged list; owners are Donatas's now)
| # | Fix | Why it matters on camera | Where | Effort |
|---|---|---|---|---|
| 1 | Print the period on every OVERVIEW ("Jan-Oct 2026, latest month Oct"); "as of" = the data's last month, not today; say when a time word in the request was not applied | the band says "DATA AS OF 2026-11-08" and nothing names a period; a viewer asks "which quarter?" | render.py / ui.overview / specbuild notes | S |
| 2 | Do not title the page for the half of the question that survived; add "not shown: <KPIs>" or a gap tile (M-D, M4) | "sales and supply" gives a page titled "whether supply is safe" with one sales tile | specbuild / interview | S/M |
| 3 | Label every segment of the share bar (or a legend), axis title "% of total" (V1) | only "EMEA 38%" is labelled; three unlabeled bars | render._stacked | S |
| 4 | Growth axis in percent (V2): 0.2 shown with title "%" vs tile 11.9% | reads as 0.2% | render._line | S |
| 5 | spec.py fields -> specbuild sets span/row/archetype -> journal keeps them -> .pbip uses the grid (M-A, M-B) | an approved OVERVIEW exports as the old flow layout; do not show its .pbip until fixed and reopened in Desktop | spec.py, specbuild, pbip (Martynas) | M |
| 6 | Unit-aware tile deltas ("pp", no decimals on counts, no "-0.0") (V4) | "+332,608.0 vs last month" | render._card_numbers | S |
| 7 | Reword the home chip "How are we doing in LATAM this quarter?" to "...in LATAM?" (or support quarters) | clicking the chip shows the ignored-period problem on the first screen | suggest.py / chips | S |
| 8 | Short tidy: one title + one CREATE chip, table value next to its label with "%", dedupe/rename "trap 14" data notes, sidebar toggle overlap | polish on a 2-minute video | ui/css | S |
Order: 7, 1, 3, 4, 6 first (about an hour in total, all small); 2 next; 5 only if time (else do not show an approved overview's .pbip).
If any of 1-4 is not done by 05:00: keep OVERVIEW ON but use only the paths below, which avoid the weak spots.

## B. Paths that look best (use these; each verified unless marked)
Run on `make demo` or the app, Day theme for the first dashboard and Night for one, dark text is easier to read on video.
Frame the three roles as one story: the floor asks, the manager oversees, the builder governs.

### Act 1: Worker21 (Plant-A floor, Warehouse Ops), about 40 s
Login Worker21 / Worker123. Floor buttons: "Is supply safe at my plant?" or "Deliveries on time and complete".
- Shows: a reuse-only answer for their own plant: On-Time In-Full 82.2%, card + trend, no new dashboard built, no build button.
- Then ask for something that does not exist (button "Line downtime" as Worker22 Equipment Ops, or free text). Result: "not governed yet",
  and **Ask the BI team for it** sends a request. Say: "the worker never builds, never sees another plant."
- Optional 5 s: type "How is Plant-B doing?" -> refused ("Plant-B's numbers come through your manager"). Safe, deterministic.
- Do not: type free text that guesses (say "plan my day": generic buttons), or anything with "equipment" as Worker21.

### Act 2: Manager07 (Plant-B site head), about 60 s
Login Manager07 / Manage123. Type or pick "How is Plant-B doing?" -> **Use recommended**.
- Shows: the OVERVIEW: header band, 4 tiles (On-Time In-Full 78.3% BREACH vs 90, inventory 5.5 weeks OK), bullets by product with the target line,
  trends, share by region, "Products below 90% on-time in-full" table, then "How this was decided" (the receipts).
- Say what the red tile means and that every number is computed by code from governed data (Synthetic data footer).
- Change one filter (Market = Germany): OTIF becomes 80.1% BREACH, inventory flips to WATCH; the dashboard follows (verified by Martynas, 3c).
- Toggle Day/Night once.
- Then **Send to the BI team for approval** (shows the handoff to Act 3).
- Optional: "Is supply safe for Plant-B?" -> a smaller OVERVIEW (3 tiles, 2 bullets, 2 trends, table).
- Do not (until fixed): "this quarter", any year, "sales and supply", "patient adherence", "Eylea in Japan, but not Japan", the LATAM chip, Plant-A.

### Act 3: Builder12 (BI team, whole company), about 90 s
Login Builder12 / Admin123.
1. **Inbox first**: the worker request ("line downtime for Worker22") and the manager's OVERVIEW are waiting. Open the manager's: **Review**, pick an
   owner from the list (do not type a free name: it accepts anything), **Create the report**. Show the journal line: who asked, who approved,
   spec hash, lint "10 pass, 0 warn, 0 block". This is the governance beat.
2. **Reuse before build**: "Net sales for Eylea in Japan" -> REUSE (EUR 252.5 M, -1.7% vs forecast), one lint warn RULE-005 (model not certified):
   a good moment to say "it warns, it does not hide". Or "Xarelto net sales in Germany" -> REUSE EUR 180.4 M, lint clean.
3. **The REQ-0001 beat** (BUILD_PLAN beat 3-4): use the phrase "Nubeqa net sales growth and forecast variance globally by country." -> **EXTEND**,
   card values: net sales EUR 3,347.7 M, growth -14.1%, forecast variance EUR -50.8 M, no lint issues. Do NOT use
   "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country." (that wording gives CREATE and a different page).
4. **Estate**: Catalog health / Orphan rescue tabs (AST-0091 successor). UNSEEN by me: run once before recording. Repair-plan panel only if Donatas hooks it in.
5. **Export**: the hand-built overview .pbip (opened in Desktop as laid out), or the REQ-0001 export. Not an approved OVERVIEW's .pbip until fix 5.
Close on the headline number (from code, over 150 requests) if the README has it.

## C. Pre-record checklist
- Fresh data dir (`make demo` copies demo/steward_seed): the inbox must be empty at the start of Act 1 and 2 so the handoffs are the ones you record.
- LLM: record with the cache that was warmed (`make warm`, Donatas), or with STEWARD_USE_LLM=off; say which in the README. Same sentences give the same
  dashboards only on cache or off.
- Window about 1440 wide, one theme per take, sidebar collapsed for dashboards (the open sidebar clips the day-theme trend axes, V9).
- Run each path once on the exact build you will record; the exact numbers above come from the current main (b205b94cbb4bb804 for 1a).
- Phone width, two real browser windows, live LLM, the estate tabs: UNSEEN, give them 5 minutes before the recording.
