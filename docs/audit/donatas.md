# Audit: Donatas (phase 1, blind) — Sat 7 Nov 18:50

Deep stretch: **10 render + UI**, **11 governance**, **end-to-end demo flow per role** (raw material for the pipeline slide).
Every number below comes from a command I ran on main at d2f453a+ (scripts in my scratchpad, reproducible by the
one-liners shown). Clean state = `STEWARD_DATA_DIR=<empty dir>`; the LLM was Gemini `gemini-3.5-flash` via
`BackendClient`, which returned **429 on every call** during the audit (quota), so the live-LLM rows show the
outage path.

**Duplicates (rule 18:50).** Gajus pushed first (6428f24), so these ideas are his and I only add evidence:
- labels vs ids on the interview path = **his F1**;
- per-step receipts = **his bold idea**;
- data-first layout ranking = **his node 8**.

My replacements are in "More optimisations" and "More bold ideas" at the end.

## TL;DR (the five things that matter)
1. **Independent confirmation of Gajus's F1 (his idea, my extra evidence).** I found it on my own, blind, by a
   different route. A sweep over every product x {"net sales in Germany", "net sales by month", "OTIF"} shows
   **5 of 21 flip** REUSE/EXTEND -> CREATE on `ask_intent`. The same flip happens on the **LLM-outage path**:
   `pipeline._ask_ai` falls back to the interview's rules intent, which carries labels. So when Gemini 429s, even the
   expert path builds what already exists.
2. **"This quarter" is silently dropped.** "How are we doing in LATAM this quarter?" shows **EUR 2,431.4 M**, which is
   Jan-Oct 2026. The last 3 months are **EUR 692.0 M**. No card says which period it covers.
3. **Approvals feed back into search and poison later verdicts.** In my working data dir, "All Pharma Growth Legacy"
   (AST-0335) was extended three times, by "LATAM this quarter", "pharma sales last month" and "is supply safe for
   plant-b" (journal lines 4-6). With that state, "Nubeqa net sales vs forecast" EXTENDs **AST-0335-v4** (refreshed
   today, 0 views). On a clean dir it EXTENDs **AST-0143**. A rehearsal changes the stage demo.
4. **The renderer cannot express a reading sequence.** `RenderedDashboard` (`steward/render.py:43`) is four buckets:
   cards, gaps, figures, tables. The UI draws them as cards row -> 2-column figures -> tables (`steward_app.py:333-358`).
   Margiris's step order (answer -> good/bad -> when -> where -> act) is lost however `render()` iterates. Agreeing to
   "draw in step order" (ask 1107-182430) only helps once the output itself is an ordered list.
5. **Governance accepts anything as an owner.** I approved a CREATE with owner "Mickey Mouse": it was journaled and
   catalogued (`new-on-time-in-full-inventory-coverage-demand-forecast-accuracy-001`, owner "Mickey Mouse"). The data
   pack has an Owners sheet. Panu point 9 (ownership has to be explainable) is exactly this.

---

## End-to-end trace (the pipeline slide raw material)

Command: `STEWARD_CATALOG=datapack STEWARD_USE_LLM=off STEWARD_DATA_DIR=<clean> python trace.py` (ask -> build(user) -> render).

| Request | Rules path (CLI, LLM off) | Interview / AI path (UI, or LLM down) | Worker / Manager / Builder view |
|---|---|---|---|
| How are we doing in LATAM this quarter? | CLARIFY ("I don't recognise 'doing'") | EXTEND AST-0015 "All Pharma Net Sales New", 50 %, "Missing: metric Net Sales" (contradicts its own title) | M/B: 4 cards (NS, NS growth, FV, OTIF) + line + **empty** table; worker: OTIF cut. Period = Jan-Oct, not the quarter |
| Is supply safe for Plant-B? | CLARIFY ("I don't recognise supply, safe, Plant") | CREATE OTIF + Inventory Coverage + Demand Forecast Accuracy, filter site=Plant-B | Cards 78.3 % / 5.5 wk / 83.7 %, table "Products below 90 % OTIF" 7 rows |
| Xarelto net sales in Germany | **REUSE AST-0191** | **CREATE** (label vs id bug) | 1 card EUR 180.4 M, -4.4 % vs forecast + line; same for all roles |
| REQ-0001 Nubeqa global (with metadata) | CLARIFY (metadata conflict, golden) | n/a | n/a |
| Nubeqa NS vs forecast globally by month | EXTEND AST-0143 "Nubeqa Demand - EMEA" (an **EMEA** asset for a **global** question) | — | W: 2 cards + line; M/B: + bar by country + **empty** table "Countries > 10 % off" |
| Mine: "OEE of my packaging line and scrap cost per batch for Plant-A" | NOT_FEASIBLE, "nearest governed: Market Access Coverage, Demand Forecast Accuracy" (irrelevant) | — | — |

**Latency (LLM off):** startup 0.6 s, ask 0.00-0.08 s, build 0.01-0.02 s, render 0.2 s cold and 0.01-0.03 s warm.
Rendering is never the bottleneck.
**Latency and calls (LLM on, all 429):** ask 4.5-5.3 s = 3 calls (interview JSON, investigate JSON, explain text).
build 1.9-2.3 s **per role** = 1 call (layout JSON, always fell back to `template`). The UI then adds 1 takeaway call.
**About 5 LLM calls and about 7 s per question before anything is shown**, and with quota gone every one of them is
wasted latency. There is no circuit breaker: after the first 429 the next four calls still go out.

**UI handoff (AppTest, LLM off, clean dir):** Manager07 asks "Is supply safe for Plant-B?" -> 1 interview turn ->
"Use recommended" -> "Send to the BI team" -> log out -> Builder12 sees 1 "Review" -> "Create the report" with an
owner -> journaled "Builder12 (builder), requested by Manager07 (management)", spec ee7ee0fe51544bab saved.
**2.0 s wall clock for the whole flow. No exceptions.** The flow works; what it produces is the problem.

### Pipeline slide (Panu point 8): one row per step, the Plant-B example
| Step | In | Out (Plant-B) | Ours vs other teams |
|---|---|---|---|
| 1 Login / role | user | Manager07, management, Plant-B | the role sets the scope and the envelope |
| 2 Understand | "Is supply safe for Plant-B?" | Intent: theme supply_health, OTIF+IC+DFA, site Plant-B | ids validated by code |
| 3 Grill-me | Intent | 1 question ("Yes, use these / Add net sales"), "Use recommended" | short, stops on confidence |
| 4 Search existing | Intent | ranked assets (BM25+trigram+structure, RRF) | the reuse-first evidence |
| 5 Decide | hits | CREATE (nothing covers it) | rules, not the LLM |
| 6 Spec + layout | decision + role | DashboardSpec, 3 cards + trend + table | the gap is never a number |
| 7 Lint | spec | 10 pass, 0 block | approve gate |
| 8 Render | spec + data | 78.3 % OTIF, 7 products below 90 % | deterministic, from the data pack |
| 9 Approve | builder + owner | journal line + spec hash + catalog entry | maker AI, checker human |
| 10 Export | approved spec | .PBIP | ends in Bayer's tool |

---

## Node by node

### 0 Users and hierarchy (short)
1. In/out: login -> `User(role, plant, department)`; `can()`, `can_see()`, `plants`.
2. Now: `steward/auth.py:25-31` (action sets), `:94-108` (visibility via Supply_Operations).
3. Assumption: three roles are enough, and a demo mock is fine.
4. Attack: authorisation lives only in the UI. `Governance.approve(result, actor: str)` (`governance.py:31`) has no
   user or role, so any caller can approve. The worker envelope cuts OTIF from a LATAM answer (trace above), which is
   the one plant-relevant number in it. In the UI the worker goes through `worker.reuse_only` with `sites=[user.plant]`,
   so the cut does not show there, but `Steward.build(user=worker)` is inconsistent with it.
5. Optimise: pass `User` into `Governance` and check `user.can("approve")` there. One line, and it turns the
   permission into a tested invariant.
6. 0 to 1: the role is a **reading contract**, not a filter: worker = "can I act on my shift", manager = "is my plant
   on track", builder = "is the estate healthy". Each has its own first sentence.
7. S (0.5 h) / an approve that cannot be bypassed. 8. Verdict: **keep + improve**.

### 1 Intake (short)
1. Chips, chat box, worker department buttons -> text.
2. `steward_app.py:965-1000`, `worker_view.py`.
4. Attack: the builder screen shows 6 action buttons on one review (Create / Send back / Draft with AI / Approve for
   the floor / Propose successor / Retire candidate), which is a lot of decisions in one place. The chips are polished
   data-pack requests, and Panu prefers our own ambiguous ones.
8. Verdict: **keep**.

### 2 Understanding (short, but see TL;DR 1)
1. Text -> Intent (LLM) or ParsedQuestion (rules).
2. `intent.py:72-92` `to_parsed_question`, `:102-108` `intent_from_parsed` (id -> **label**).
4. Attack: **the two paths produce different filter vocabularies.** Repro (LLM off, clean dir):
   ```
   rules  filters {'product': 'P-XAR', 'market': 'DE'}            -> REUSE AST-0191
   intent filters {'product': 'Xarelto', 'market': 'DE'} +month    -> CREATE
   label only (no month)                                           -> CREATE   <- the cause
   month only (id kept)                                            -> REUSE AST-0191
   ```
   Sweep over every product x {"net sales in Germany", "net sales by month", "OTIF"}: **5 of 21 flip** (Eylea DE,
   Lynkuet OTIF, Nubeqa DE: EXTEND -> CREATE; Xarelto DE and Xarelto by month: REUSE -> CREATE).
   Also: the rules path CLARIFYs "Is supply safe for Plant-B?" and "How are we doing in LATAM", while the interview
   path answers both. The stage demo with `make demo` (LLM off, CLI path) and the live UI therefore tell different
   stories for the headline questions.
   "This quarter" -> `dims ['quarter']` and no month filter, so the dashboard covers all 10 months.
5. Optimise: one canonical vocabulary (ids) at the Intent boundary, labels only at display. Add a test that runs the
   golden questions through `ask_intent(intent_from_parsed(...))` and asserts the same verdict. Map relative periods
   ("this quarter", "last month") to `month_from/month_to` filters.
7. S (1-2 h) / stops the UI from proposing new builds that already exist. **This is the #1 fix of the whole audit.**
8. Verdict: **fix now**.

### 3 Grill-me (short)
- Manager, Plant-B: 1 question, then "Use recommended". That fits Panu point 1 (short, early stop).
- Attack: the options include "Add net sales" for a supply question, an odd suggestion for a plant manager.
- Verdict: **keep**.

### 4 Search (short)
- Attack: an **EMEA** asset (AST-0143 "Nubeqa Demand - EMEA") is the EXTEND base for a **global** question. Market
  scope does not gate the candidate.
- Attack (with 11): our own approved copies rank first because "refreshed today" lifts trust (TL;DR 3).
- Verdict: **improve** (scope compatibility as a hard filter for EXTEND).

### 5 Decision (short)
- Attack: EXTEND of an asset titled "…Legacy" (AST-0335), three times in a row. A lifecycle flag (legacy, retire
  candidate) should forbid EXTEND and point to the successor. Supply-safety and LATAM-sales questions both EXTENDed the
  same commercial "Growth" report at 50-57 % coverage.
- Attack: on REUSE, "Xarelto Forecast New" (not certified, refreshed **308 days ago**) wins, while the explanation
  warns about a conflicting definition in another Xarelto report. Stale + uncertified REUSE should at least be
  "REUSE with a refresh request".
- Verdict: **improve**.

### 6 Explanation (short)
- Attack: "Extend 'All Pharma Net Sales New' … Missing: metric 'Net Sales'". The text contradicts itself, so a judge
  stops trusting it. NOT_FEASIBLE "nearest governed" lists Market Access Coverage for an OEE question: nearest by
  string, not by meaning. Better to say "nothing close; here is who defines manufacturing KPIs".
- Verdict: **improve**.

### 7 Data and semantics (short)
- `semantic.compute` is fast (render 0.01 s warm) and honest about forecast_like rows (the DQ note appears on every
  sales dashboard).
- Attack: `prior_month` comparisons on OTIF print "-4.1 vs last month" without "pp"; inventory prints "-0.0 vs last
  month". Units come from `is_fraction`, which does not cover KPIs stored as percent numbers.
- Verdict: **keep + small fixes**.

### 8 Spec and layout (short)
- With Gemini at 429, every build tried the layout call (~2 s per role) and fell back to `template`. All `step` = 0.
  The AI layout never showed in any of my traces. On stage that means the AI-ordered page depends on quota.
- LATAM worker spec: two cards titled "… net sales" and "… net sales " (trailing space, truncated). Titles need to
  differ by what the card compares.
- Verdict: **keep the contract; cache the layout per (spec_hash, role)**, so a rehearsed question never calls again.

### 9 Lint (short)
- "10 pass, 0 warn, 0 block" on every dashboard I traced, including the LATAM one that silently ignores "this quarter"
  and the EMEA-for-global EXTEND. Lint checks the spec's shape, not whether it answers the question.
- 0 to 1: a **RULE-ANSWER** lint: every scope word the user typed (period, site, market) must appear in `spec.filters`,
  or be listed as "not applied". That is cheap and it catches TL;DR 2.
- Verdict: **improve**.

### 10 Render + UI (DEEP)
1. **In / out.** `DashboardSpec` + frames + filter overrides -> `RenderedDashboard(cards, gaps, figures, tables,
   footer, dq)`. The UI (`render_dashboard`, `steward_app.py:302-366`) lays it out per role.
2. **How it works now.**
   - `render.py:62-74`: walks pages/visuals in spec order and dispatches by type into **separate buckets**.
   - Cards: `forecast` comparison = period total vs forecast; `prior_month` = last vs previous month (`:95-117`).
   - **KPI-042 is special-cased in three places** (`:98-102`, `:172-186`, plus `exclude_zero`): comparison maths lives
     in the renderer, not in `semantic`.
   - The UI applies **a second role cut** on top of the layout envelope: `keep = max(2, 5 - len(gaps))` tiles and
     `figures[:2]` for the non-governance view (`steward_app.py:335-351`).
3. **Assumption.** "A dashboard is tiles on top, charts below." That is true for a BI page, not for an answer.
4. **Attack (repro + result).**
   - *Reading order lost:* step order cannot survive the buckets (TL;DR 4). Even with the step-order render agreed in
     ask 1107-182430, cards still go first and tables last.
   - *No period on any card:* LATAM "net sales EUR 2,431.4 M" does not say Jan-Oct 2026. A floor viewer reads it as
     "this quarter" because that is what they asked.
   - *Good/bad is not shown:* `prior_month` tone is always `neutral` (`render.py:116`). OTIF at Plant-B fell 4.1
     points and the card is grey. The "is it good or bad" step of the reading sequence is not on screen.
   - *Silent drops, against our own rule:* a bar on an `ASSET_LEVEL_KPIS` measure returns with no message (`:156-157`).
     Line, bar and table swallow `ValueError` and vanish (`:140-141`, `:160-161`, `:193-194`). `prior_month` with
     fewer than 2 months falls back to the period total without saying so (`:108-117`). Martynas's "never a silent
     drop" holds for the role cut, not for the renderer.
   - *Empty answers shown as empty tables:* "Countries more than 10 % off forecast" renders with 0 rows for Nubeqa and
     LATAM. The UI caption says "No rows past the threshold". That is good news, but it reads like a broken table.
   - *Two role cuts:* layout envelope (layout.py) **and** `keep`/`figures[:2]` in the UI. They can disagree, and the
     second one is not recorded in `spec.provenance`, so the journal's spec does not equal what the requester saw.
5. **Optimise.**
   - `RenderedDashboard.blocks: list[Block]`, in step order, each block = (step question, visual, numbers, notes). The
     UI walks `blocks`; the buckets become a derived view for the expert grid. That is ~1 h in render.py + ~1 h in
     the UI.
   - Every card carries `period` ("Jan-Oct 2026", "Oct vs Sep") and `scope` ("Plant-B"), from the effective filters.
   - Tone from direction: each KPI has a better-is (up/down) in `measures.json`. Colour the delta by it; with a
     governed target, use the target.
   - Every early `return` becomes a `GapView`-like "not drawn because …" note.
   - An empty threshold table becomes a positive card: "No country is more than 10 % off forecast".
   - Delete the UI's second cut; layout.py is the only place that cuts, and it records what it cut.
6. **0 to 1: the dashboard reads as an answer** (receipts per number: see Gajus's per-step receipts, his idea). The page reads top to bottom as Margiris's sequence,
   and each block is headed by its question: "**Is supply safe at Plant-B?** Not fully: OTIF 78.3 % (Oct), down 4.1
   pp vs Sep, below the 90 % line." Then "Where from?" -> the 7 products below 90 %. Every number has a **receipt**
   on click: KPI id + governed definition + filters + row count + source model + spec hash. No other team will
   have numbers that can prove themselves, and it is the same data we already put in the footer and journal, just
   moved next to the number.
7. **Effort / impact.** M (3-4 h for blocks + period + tone + receipts) / the floor viewer gets an answer instead of
   a tile wall; the judge sees governance on every number, not in a footer.
8. **Verdict: improve** (keep Plotly and the determinism; replace the bucket output).

### 11 Governance (DEEP)
1. **In / out.** `StewardResult` + actor (+ owner) -> journal line (JSONL), catalog change (`catalog_changes.json`),
   spec file by hash (`data/steward/specs/<hash>.json`).
2. **How it works now.** `governance.py:31-58` approve: CLARIFY / lint block / NOT_FEASIBLE refused, EXTEND copies the
   asset as `<family>-v<n+1>` (`:89-118`), CREATE adds a `draft` (`:120-145`). `reject` needs a reason (`:60-63`).
   `propose` journals with `verdict=CLARIFY` as a placeholder (`:65-80`).
3. **Assumption.** "Approve = write the JSONL; the catalog change makes the next search see it." That is right for a
   demo, and it is what produces the feedback loop.
4. **Attack (repro + result).**
   - *Self-reinforcing catalog (TL;DR 3):* `data/steward/journal.jsonl` lines 4-6 extended AST-0335 "All Pharma
     Growth Legacy" -> v2 -> v3 -> v4 with three unrelated questions. `_extend` sets `last_refreshed=as_of`
     (`:112`), so the copy is "fresh" and wins the next search. Each EXTEND also appends metrics, so the asset grows
     into a junk drawer. Nubeqa: AST-0335-v4 (dirty) vs AST-0143 (clean).
   - *Owner is free text:* "Mickey Mouse" accepted (AppTest repro above). The footer then shows an owner that
     `semantic.owner_info` cannot find.
   - *No permission in the core:* `approve()` takes `actor: str`; only the button checks `user.can("approve")`.
   - *Scope lost on CREATE:* the spec has `filters={'site': 'Plant-B'}`, but `_create` writes `filters={}` (`:135`).
     The next "supply at Plant-B" search will not see that the new asset is Plant-B's. The title is the question
     text ("Is supply safe for Plant-B") and the id is 72 characters long.
   - *Send back goes nowhere:* `reject` journals it, the queue item is popped (`steward_app.py:729`), and the
     requester never sees the reason (the queue is session-only; Panu Q&A "still open").
   - *Journal is not tamper-evident:* append-only by convention only. The spec hash covers the spec, but nothing chains
     the lines. "Reset demo" deletes the journal and changes but leaves `specs/` and `floor_requests.jsonl`.
   - *`propose` pretends to be a CLARIFY verdict:* any report that counts verdicts from the journal counts proposals
     as clarifications.
5. **Optimise.**
   - EXTEND makes a **pending version** (status `draft`, not `active`) and keeps the original's `last_refreshed`, so
     trust only rises after a real refresh. Or, simplest: search ignores `catalog_changes` assets for EXTEND bases
     unless they are certified.
   - Owner = a pick-list from the Owners sheet (active owners for that domain), free text not allowed.
   - `Governance.approve(result, user: User, owner_id)` and check `user.can("approve")`.
   - `_create` copies `spec.filters` (site/market/product) into the artifact scope; the title is `spec.name`.
   - Journal line `prev_hash` = sha256 of the previous line: a 3-line change that makes the journal tamper-evident.
   - `JournalAction.PROPOSED` with `verdict=None`.
   - The demo runs on a **fixed data dir copied fresh at start** (`make demo` copies `demo/steward_seed/` -> tmp), so
     rehearsals never change the stage verdicts.
6. **0 to 1: governance as a lineage you can replay.** Every approved dashboard = (question, intent, decision,
   spec hash, lint, approver, requester, owner id), hash-chained. "Replay" re-runs the chain on today's data and diffs
   against the approved spec: **"this dashboard would no longer be approved: KPI-001 definition changed on …"**. That is
   estate health from the journal, not from a separate scan, and it answers Panu point 9 ("why does this asset exist,
   who owns it") with one click: the asset's journal line.
7. **Effort / impact.** S each for owner list, scope on CREATE, the permission check, hash chain and seed dir (~2 h in
   total); M for replay (3 h) / a judge can check any number's approval trail, and the stage demo is reproducible.
8. **Verdict: improve** (the model is right; the write side leaks).

### 12 PBIP (short)
- Not traced deeply (paused task). The export is gated on `lint.can_approve` (`steward_app.py:465-468`), which is
  right. Martynas still waits on `submission/pbip_open.png`.
- Verdict: **keep**.

### 13 Estate health (short)
- `health()` is 0.07 s on the pack (earlier commit e7de3ed). It does not see our own feedback-loop assets: AST-0335-v4
  (0 views, 4 metrics bolted on) is "healthy" by staleness. Add "extended N times in M days" as a smell.
- Verdict: **improve**.

### 14 Proof (short)
- 27 UI/render/governance tests pass in 13 s. **The golden sets test the rules path only**: `golden_datapack.json`
  has 3 product-filtered questions and none flips; my 21-question sweep finds 5 flips on the intent path.
  `golden_questions.json` is still the invented sample (herbicides = Crop Science, out of scope).
- Verdict: **improve** (add the intent-path parity test, retire the sample golden file or label it legacy).

### 15 LLM infrastructure (short)
- About 5 calls per question (3 in ask, 1 layout per build, 1 takeaway), ~7 s total. During the audit Gemini 429'd
  every call, and the app kept calling.
- Optimise: a circuit breaker (after one 429, LLM off for 60 s, with a UI badge "AI paused: rules mode"); a cache
  keyed on (prompt hash) for layout and takeaway; and decide whether investigate + explain need to be two calls.
- Verdict: **improve** (for the stage this is a demo-killer).

---

## Top 3 changes (ranked; Gajus's F1 fix is assumed done first, his #1)
1. **Scope honesty end to end** (nodes 2/9/10, M, ~3 h).
   - Relative periods ("this quarter", "last month", "YTD") become `month_from/month_to` filters.
   - **RULE-ANSWER lint:** every scope word the user typed (period, site, market, product) is either in
     `spec.filters` or listed as "not applied". "You asked for this quarter; this shows Jan-Oct" warns, or blocks
     approve.
   - Period and scope are printed on every card.
   - Today the LATAM answer is 3.5x the right number (EUR 2,431 M vs 692 M) with all lints passing.
2. **Governance write side: no self-poisoning, real owners, reproducible demo** (node 11, S-M, ~2 h).
   - EXTEND makes a draft version and keeps the original refresh date.
   - EXTEND is forbidden on legacy or retire-candidate assets.
   - Owner = a pick-list from the Owners sheet.
   - CREATE copies `spec.filters` into the asset scope.
   - `make demo` copies a seeded data dir.
3. **Render an ordered answer, not buckets** (node 10, M, ~2 h).
   - `RenderedDashboard.blocks` in step order, each headed by its question.
   - The only role cut is in layout.py (delete the UI's second cut).
   - No silent drops: every visual that is not drawn gets a one-line reason.
   - An empty threshold table becomes a positive statement.
   - This is the precondition for Gajus's data-first layout and Margiris's sequence to be visible at all.

## One bold idea for the chain (replaces my "receipt per number", which duplicates Gajus's receipts)
**The approval is a contract that re-checks itself.** Each approved dashboard stores what it promised:
- KPI ids + definition versions;
- scope and filters;
- the source model and its endorsement;
- the owner id;
- the lint result;
- the numbers it showed, by spec hash.

A nightly (or on-open) **replay** runs the same spec through the chain on today's catalog and data and diffs:
- "definition of KPI-001 changed";
- "owner OWN-12 left";
- "source model refresh failing";
- "a certified asset now covers this: retire this copy";
- "this dashboard would no longer pass lint".

The diff is shown as a banner on the dashboard for viewers ("numbers since 3 Nov may be affected") and as a work
queue for builders. That is estate health derived from the journal, not a separate scan. It answers Panu point 6
(builders: "are my assets healthy?") and point 9 (why does it exist, who owns it) with the same mechanism, and it
turns governance from a gate at birth into a guarantee for the asset's life.

## More optimisations (beyond the top 3; checked against gajus.md, none duplicate)
1. **LLM circuit breaker** (node 15, S, 30 min).
   - Problem: during this audit every Gemini call returned 429, yet each question still made ~5 calls and waited ~7 s.
   - Fix: after the first 429/503, the LLM is off for 60 s, the UI shows "AI paused: rules mode", and calls resume
     on their own after that.
   - Stage insurance.
2. **Layout + takeaway memo keyed on (spec_hash, role, filters)** in the data dir (node 8/15, S).
   - A rehearsed question never calls the LLM again on stage.
   - Every role's build currently re-calls the layout (~2 s each, 3 roles = 6 s).
3. **Scope compatibility as a hard gate for an EXTEND base** (node 4/5, S).
   - Problem: the EMEA asset AST-0143 is the base for a global question today.
   - Fix: a base whose market or product scope is narrower than the ask is "EXTEND scope", stated as such, or skipped.
4. **Tone from KPI direction** (node 10, S).
   - Add `better_is: up|down` per KPI in `measures.json` and colour every delta by it.
   - Today `prior_month` is always grey (`render.py:116`); OTIF -4.1 at Plant-B shows no warning.
   - Add a "pp" unit for percentage KPIs ("-4.1 vs last month" -> "-4.1 pp").
5. **Permission check inside `Governance.approve`** (node 0/11, S, 15 min).
   - Pass `User`, not `actor: str`, and refuse unless `user.can("approve")`.
   - Turns a UI-only rule into a tested invariant.
6. **Hash-chained journal** (node 11, S, 20 min).
   - Each line carries `prev_hash`; "Reset demo" also clears `specs/` and `floor_requests.jsonl`.
   - `propose` journals with `verdict=None`, not CLARIFY.
7. **Send back reaches the requester** (node 11, S).
   - The reason goes to the requester's request log (`floor_requests.jsonl` already exists) and shows on their next
     login: "Builder12 sent back your Plant-B request: …".
   - Closes the loop Panu's point 4 implies.
8. **Fix the self-contradicting explanation** (node 6, S).
   - "Extend 'All Pharma Net Sales New' … Missing: metric 'Net Sales'" comes from a coverage computation that
     disagrees with the title.
   - Template rule: never list a missing metric whose name is in the asset title without saying why ("the title says
     Net Sales but the asset's measure is Gross Sales").

## More bold ideas (beyond the one above; not in gajus.md)
1. **Shadow the requester.**
   - When a builder opens a request, the screen shows the requester's exact view (role envelope, plant scope,
     tiles), side by side with the builder's expert view.
   - The builder approves what the person will actually see, and the journal stores both spec hashes.
   - Fixes "the journal's spec is not what the requester saw" (two role cuts today) and makes maker/checker real.
2. **Counterfactual "build less" meter.**
   - Every ruling records what a naive tool would have done (CREATE a new dashboard) against what we did (REUSE or
     EXTEND).
   - The Journal tab sums it: "this week: 14 requests, 9 answered by existing assets, 3 extensions, 2 new; 9
     dashboards not built, 23 duplicate KPIs avoided".
   - A qualitative-plus-quantitative pilot metric (Panu point 7) that the product produces itself, from the journal
     we already write.
3. **Answer-first floor mode with a "this changed" push.**
   - A worker's approved numbers are re-rendered on every login.
   - Only the ones that crossed a threshold since the last visit are shown first ("OTIF at Plant-A dropped below
     90 % on Tuesday"), with one tap to the governed dashboard.
   - The floor viewer stops looking for dashboards; the dashboards find them.
   - Uses the same replay machinery as the bold idea above.
