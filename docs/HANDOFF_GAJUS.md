# Handoff: Gajus -> Donatas (Sun 8 Nov, 01:50)

Gajus's Claude is out of credits. Donatas is now team lead and owns every file Gajus owned (OWNERS updated, CLAUDE.md
escalations now go to `say donatas`). Plan of record: docs/audit/DECISION.md. Decisions log: NOTES.md.

## Clock
Freeze 05:00 · video 05:00-07:30 · submit 08:00 (hard deadline 10:00, sinceai.app).
OVERVIEW rule (user-approved): one switch turns it off; if `make test` is not green AND the Mac .app self-test does not
pass by 04:00, it ships OFF. Old spec hashes + the 73 labelled golden cases must stay unchanged; layout falls back to the
template on any failure.

## Open items (in order)
1. OVERVIEW (Donatas): spec.py fields (OK given 01:48) -> specbuild archetype -> layout envelope -> render branch.
   Martynas pbip side 4b45a43, Margiris/Donatas lint 4a80529 are on main.
2. Final warm near the freeze (Donatas only): `make warm` (= tools/warm_layout.py now) then commit demo/cache + layout cache.
3. Final Mac .app: `make app-build` -> build/selftest.txt must say RESULT: PASS. Last PASS: after 9bac33a (5.8 s).
   A rebuild with the searchbox was running at handoff (log: Gajus's scratchpad); re-run it after OVERVIEW lands.
4. Windows .exe (Martynas) after the freeze; he must `uv pip install streamlit-searchbox==0.1.24` first.
5. Margiris: `git rm eval/eval.py eval/holdout.jsonl` (broken since T3.7, no test imports them). OWNERS lets Donatas do it.
6. Not started (Tier 3, cut if no time): T3.1 value-of-information; seeding demo learned suggestions.

## Context for OVERVIEW (where things are)
- `steward/specbuild.py`: `spec_hash()` l.52 (drop span/row/archetype when default: the hash test pins old hashes);
  `build_spec()` l.80; `_legal()` l.369 filters the visual menu through `semantic.profile`/`check_visual` -
  new types (kpi_strip, bullet, diverging_bar, stacked_100) must pass it or they are silently dropped.
- `steward/layout.py`: `envelope_for(role)` l.130 fails closed to worker; `plan()` l.165 validates an LLM proposal and
  returns (page, source) - any exception must return the template page. Disk cache: CACHE_DIR / STEWARD_LAYOUT_CACHE
  (frozen app: ROOT/layout_cache). New archetype = new cache key, so re-warm after it lands.
- `steward/receipts.py` "Build the dashboard" receipt reads `spec.provenance['layout_source'|'layout_role'|'layout_hidden']`:
  keep writing them for OVERVIEW pages.
- Demo questions that become OVERVIEW: "How efficiently is this plant running?" (plant_efficiency),
  "How are we doing in LATAM this quarter?" (business_performance), "Is supply safe for Plant-B?" (supply_health).
  "Xarelto net sales in Germany" (REUSE AST-0191) and REQ-0001 (CREATE) must not change.
- Tests to watch: tests/bi_steward/test_golden.py (73 cases, both paths), test_receipts.py, test_app*.py, test_suggest.py.

## What Gajus shipped tonight (all on main)
- T2.5 receipt strip (1314949): `steward/receipts.py`, "How this was decided" under Why.
- App: self-test race fix (e537949); Api.set_theme + &theme= (Donatas design fixes).
- T3.1 interview (f208de5): manager's "this plant" = login plant; model-vs-rules agreement decides what to ask.
- T3.7 (26a0e46): data pack is the only catalog; labelled data-pack cases = verdict contract; legacy backend gone.
- Autofill (4e6271d, 9bac33a, 648d1fa): `steward/suggest.py`. Memory in the user app-data folder
  (STEWARD_MEMORY_DIR overrides; tests use tmp): suggestions.json (chips, >=2 people, same role+plant, workers +dept)
  and requests.jsonl (EVERY first message + outcome, for backtests). `make backtest` replays it. A picked team request
  reuses the confirmed Intent: 0 questions, 0 AI calls. Dropdown = streamlit-searchbox 0.1.24 (.st-key-bs-typeahead),
  import guarded. Size/pruning: later (user).

## Rules that still apply
No secrets on the board/Discord/repo; Gemini key only by DM; never --no-verify; only Donatas runs make warm; only
Margiris commits eval/results.json; answer asks only with your person's yes/no; NOTES.md line per decision.
