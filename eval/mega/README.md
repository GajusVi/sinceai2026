# Mega backtest: is the app ready for the demo?

`.venv/Scripts/python.exe eval/mega_backtest.py` (Mac: `.venv/bin/python`; `make mega` once Donatas adds it) runs 111 simulated people through the app for 40 working days on the real
data pack (360 assets), then 20 days on the 5,000-asset synthetic pack (`tools/make_large_pack.py` builds it if it is missing).
It writes `eval/mega/out/<stamp>/READINESS.md`, which gives one verdict (READY / READY WITH CAVEATS / NOT READY) and the evidence for it.

```
.venv/Scripts/python.exe eval/mega_backtest.py --pack real --days 10   # quick
.venv/Scripts/python.exe eval/mega_backtest.py --llm --days 3          # live model (slow, costs credits)
```
Runtime in rules mode: about 15-20 s per simulated day on the real pack (`--days`, default 40); the large pack is slower and runs 20 days (`--large-days`). `--report-only --out <dir>` rebuilds the report.

## Who is simulated (personas.py)
- **100 workers**, spread over every plant in the pack (the CMO counts 1/3 as much), in 4 departments, with 3 sub-roles
  each (e.g. Shift lead, Warehouse operator, Inventory clerk). Each one has a usage rate, preferred channels
  (buttons, chat, Other department), patience, savvy (precise words, vague words or typos) and a chance of escalating.
- **10 managers**: Site head x3, Operations director x2, Finance controller x2, Commercial lead x2, Shareholder/exec x1
  (with a company-wide grant). Each uses the typeahead (the search box with colleagues' requests) or the interview.
- **1 builder (admin)**: works the approvals queue (approve or send back, lint gate respected), floor requests
  (grant, start, decline), expert-mode asks from the pack's Business_Requests, a weekly estate health check and PBIP exports.

## What each interaction records (interactions.jsonl = the synthetic usage data)
Channel, whether search/typeahead was used and whether it hit, the questions asked and the replies (transcript),
the verdict, the asset, the spec, lint, what was on the page (cards, tiles, charts, gaps, data-quality notes, filters, sample
values), the metrics wanted, covered and missing, whether the expectation was met, a 1-5 score with friction tags,
any escalation, latency, and the notices received.

## Expectations (scenarios.py, written before looking at the engine)
`answer` (the wanted numbers, with values on the page), `not_governed` (an honest "not measured yet"), `refuse` (another
plant), `honest_no` (sales questions on the floor), `clarify` (off-topic text or a product that is not ours).

## Gates (report.py)
G1 no crashes · G2 plant scope holds · G3 expectation met >= 85% · G4 happy >= 75% · G5 interview median <= 3 and
p95 <= 5 questions · G6 latency · G7 display problems <= 2% of pages · G8 escalations decided and seen · G9 PBIP
export and determinism · G10 large pack vs real pack (scale).

## Limits
The people follow scripts; no LLM plays them. That tests the app's logic, flow, scope and display. It does not test
wording. Rendering is memoised per identical spec (render is deterministic), and its time is still counted in latency.
The catalog reloads every 5 days, so new approved reports show up in later searches. Isolated: every write goes to the output folder.
