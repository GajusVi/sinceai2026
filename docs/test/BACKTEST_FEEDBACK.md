# How to run the dashboard test better: feedback on Backtest 1 (Gajus's Claude, Sun 8 Nov 02:20-03:10)

Refers to: `docs/test/DASHBOARD_TEST_BRIEF.md` (the brief), `docs/test/gajus.md` (the findings), and the harness and
raw results kept in `docs/test/backtest1/`. Call it **Backtest 1**. When this is delegated again, point the next Claude
here and say "Backtest 2: same list, fix the gaps below".

## What Backtest 1 was
- Pass 1 (02:20-02:50): a script ran 8 listed iterations + 21 requests through the app's code path (LLM off) and rendered
  each spec. 0.3-2 s a case, repeatable. Found the data/wording problems (M1-M4).
- Pass 2 (03:00-03:10, only after being told the scope included the screen): Chrome, 2 dashboards, night and day.
  Found the display problems (V1-V3: unreadable share bar, growth axis in fractions, no period / wrong "as of" date).
- Pass 2 happened late because pass 1 was reported as done with "no browser" listed as a gap. That is the main process
  failure, and the first fix below.

## What was wrong with how it was run (and the fix, for the next time)
1. **The brief did not say the screen is the test.** It listed "visual list (types + rows)" and "screenshot path", which
   reads as data about the spec, not about what a person sees. Fix: the brief should name the display as the primary
   output, with a checklist (below), and say that a pipeline-only run is not a finished test.
2. **No preflight.** The Chrome extension was not connected, and the Claude reported a gap and carried on. Fix: step 0 of the
   task is "can you drive a browser? If not, reply 'cannot' for the visual half now, so someone else (or the user) takes it".
   A gap that is found at the end costs the deadline; found at minute 1 it costs nothing. The delegating Claude should also
   ask the user to connect the extension before handing it out.
3. **One tool, not two.** Scripts are good for breadth and numbers; the browser is good for display. Use both on purpose:
   - script: all cases, every role, hashes, tile values, lint, timing, regression against the last run's JSON;
   - browser: 6-8 chosen dashboards (one per archetype/chart type/state), night + day, desktop + phone width, screenshots saved.
   `docs/test/backtest1/run_iter.py` is the script (`python run_iter.py off iters1.json out1.json`, run from the repo root).
   Suggest Donatas moves it to `tools/` (his call) so it is not re-written.
4. **Pass/fail was vague.** "Expect: OVERVIEW" is not testable. Fix: the iteration table needs the expected verdict,
   archetype, tile count, chart count AND 2-3 expected numbers, taken from raw data by a separate query, not from the
   dashboard. In Backtest 1 I cross-checked one number (Plant-B OTIF: tile = latest month 78.3%, period average 80.96%);
   every iteration should have that.
5. **Period and date were not a test dimension.** Backtest 1 found the missing period only because of an odd phrase
   ("this quarter", "in 2019"). Make time a column: the request's period, the period the data covers, what the page says,
   and the "as of" date versus the data's last month.
6. **Two input paths exist and were tested once.** "Use recommended" and answering the interview questions can give
   different specs (the UI tells the user which KPIs are not measured; my script path did not). Test both, and test typed
   text versus the example chips.
7. **LLM on and off both matter.** Only LLM-off was run (deterministic, safe), but the stage uses layout cache / LLM. Name one
   run with the LLM on and note the model, and compare spec hashes and layout_source with the off run.
8. **The split by person overlapped.** Gajus's and Margiris's Claudes each had "break attempts", and split by role, not by
   dimension. Fix: split by what is tested (data/lint/verdict vs display/themes/widths vs cross-user/inbox/export), share
   one harness and one iteration table, and give each Claude a different set of break attempts up front.
9. **Evidence got lost.** Chrome screenshots land in a temp folder with names like `screenshot-1794098065955-4.jpg`.
   Fix: save each as `<iteration>-<theme>-<width>.jpg` in a gitignored `docs/test/shots/` or the scratchpad, and list the
   path in the table. (I cited the temp folder; it will not survive.)
10. **Severity rubric has no "display" class.** "MAJOR: misleading or unreadable" worked (V1/V2), but add examples so
    two testers rate the same: wrong unit on an axis = MAJOR; unlabeled legend segment = MAJOR; decimal on a count = MINOR.
11. **No time boxes inside the deadline.** One deadline (03:30) for everything. Fix: staged deliverables, e.g. +20 min
    the iteration table (script), +40 min the screens, +50 min the report and the `done` message.
12. **No regression loop.** Nothing is compared to a baseline. Fix: keep each run's JSON (`out1.json`) and diff the next run
    (hash, tiles, visual list, lint) so a fix that changes a hash is seen at once; the three pinned hashes are already a start.

## Visual checklist to add to the brief (what Backtest 1 should have looked at from the start)
For each dashboard, in night and day, at desktop width and at ~390 px (use `node <taste>/scripts/shoot.mjs --w 390`, the
browser window resize did not change the page width):
- **Period and date:** does the page say what period the numbers cover? Is "as of" the data's last month, not today?
  Do the tile notes say "latest month" or "period"? Does a time word in the request show up on the page?
- **Header band and tiles:** title once, verdict once, status words (BREACH / OK) match the colour, delta units correct
  ("pp", "%", no decimals on counts), no "-0.0".
- **Chart choice vs data:** bullet has a visible target and a label; trend has month ticks to the last month and a
  forecast line where there is one; share bars label every segment or have a legend; diverging bars have a zero line.
- **Axes and units:** axis title matches the number (a fraction is not shown as "%"), titles use one style, nothing is clipped.
- **Grid:** rows balance (no short card beside tall ones, no orphan row), nothing overlaps at narrow width, charts stack on phone.
- **Tables:** unit in the header or value, numbers next to labels, header style follows the theme; the empty state says so.
- **States:** "n/a", gap tile, empty chart, long product names, a one-country selection, refusal text.
- **Chrome around it:** sidebar collapsed and open, receipts strip, data-quality notes (jargon, repeats), the sidebar status line.

## Prompt for the next delegation (copy)
"Backtest 2 of the dashboard system. Read docs/test/BACKTEST_FEEDBACK.md and docs/test/gajus.md first. Step 0: confirm you
can drive Chrome and run the harness in docs/test/backtest1/; if not, reply 'cannot' for that half now. Re-run the same 29 cases
(`iters1.json`, `iters2.json`) and diff against `out1.json`/`out2.json`, then do the screen checklist on the cases I name, in
night and day at desktop and 390 px, saving screenshots as <case>-<theme>-<width>.jpg. Report what changed since Backtest 1: each
finding fixed, still open, or new. Read-only except docs/test/."

## What I would keep
The script (fast, repeatable, covers every role), the break attempts (they found M1-M4), and the explicit severity labels.
Backtest 1's open findings (M1-M4, V1-V11) are the first checklist for Backtest 2.
