# Audit: Gajus's Claude (Sat 7 Nov 18:40, main at dfed228)

Deep stretch: 0 hierarchy, 1 intake, 2 understanding, 3 grill-me, 6 explanation, 8 layout. Other nodes are covered
more briefly.

**Method.** Every number below comes from running code, in rules mode (LLM off) on the data pack, as_of 2026-11-06.
- Request traces: the brief's 4 requests plus 3 of my own, each run as builder, management and worker.
- Labelled cases: data/holdout/verdicts.jsonl plus golden_datapack.json (30 rows).
- Estate: all 150 data-pack requests.
- AI calls: counted with a counting fake LLM.
- Scripts: run inline from the scratchpad, not committed (read-only audit).

## Headline: the main path is not the measured path

The app has **two understanding paths**:
- **Expert:** `Steward.ask`, the rules parser or the LLM in expert mode.
- **Novice:** the grill-me interview, then `Steward.ask_intent`.

Eval, golden questions and the hold-out score only the expert path (eval/eval_steward.py:129 calls `s.ask`).
The novice path is the default in the UI, the one Panu saw and the one judges will click. Nobody measures it, and it
is broken in two ways that make us **build dashboards that already exist**, the exact opposite of Panu's point 3.

| Finding | Evidence | Effect |
|---|---|---|
| **F1. Product names, not ids, reach the engine.** `Intent` stores product names (`intent_from_parsed`: "P-NUB -> Nubeqa", intent.py:101); `Intent.to_parsed_question` (intent.py:72-96) passes them on as filters: `{'product': 'Xarelto'}` where the engine expects `P-XAR`. | "Xarelto net sales in Germany": expert path REUSE AST-0191; interview path CREATE. Same intent with the id filter: REUSE. | Labelled non-CLARIFY cases (9): expert 7/9, interview **3/9**, interview with ids mapped back **7/9**. Every labelled REUSE (4/4) becomes EXTEND or CREATE on the novice path. |
| **F2. The decision only sees the top-40 search hits.** `CatalogSearch.search(limit=40)` (search/engine.py:28), then `decide` scores those hits only (decision/engine.py:162). | 150 data-pack requests on the interview path: **26 (17%) are CREATE with top-40 and EXTEND with all assets**, and still 26 after the F1 id fix. All hits cost 34 ms per request instead of 16 ms. | False CREATE: an extendable asset exists but lexical/trigram rank pushed it out. This gets worse on the 5,000-asset large pack. |
| **F3. `make demo` and `make ui` run on the invented sample catalog** (19 assets incl. crop-science herbicide/fungicide, out of scope). Only `make bayer` sets `STEWARD_CATALOG=datapack`. | `Steward()` without the env var: 19 assets, `_on_datapack() False`. My 18:20 screenshot: REQ-0001 as builder showed "No dashboard yet / EXTEND / I couldn't build this one". | The "stage-safe" demo target shows no dashboard at all. (Unless someone's .env sets it; I cannot read .env.) |

**Root cause.** We grew two pipelines (parser path and Intent path) and joined them with an adapter. The adapter is
the weakest node in the chain, and the eval does not cover it.

## Node by node

### 0. Users and hierarchy (deep)
- **In / out:** login -> `User(role, plant, location, department)` -> tabs, actions, data scope, layout envelope.
- **Now:** auth.py (accounts, ACTIONS), worker.py (`can_see`, `other_plant`, `own_plant_scope`), layout.py
  `ENVELOPES`, steward_app.py tab gating.
- **Assumption:** each feature adds its own role check where it needs one.
- **Attack:**
  - The policy lives in **5 places**. No single place answers "what may a manager see and do".
  - The interview ignores the user completely: `Interviewer.start(text)` has no user. "How efficiently is my plant
    running?" as Manager07 (Plant-B) first asks "Which site do you mean?", although the login knows. With defaults
    it then scopes to Global (fixed downstream only by today's `own_plant_scope` patch).
  - Requests between people live in one browser session (08_PANU_QA open item), so the worker -> builder
    handoff cannot work across two browsers.
- **Optimise:** one policy table, `role -> {data_scope, tabs, actions, interview_depth, layout_envelope}`, read by
  every node.
- **0 to 1:** **Policy as data, shown on screen.** The same table renders as a "What you can see and why" card and
  as one slide. Governance a judge can read in 10 seconds, and the thing that sets our chain apart.
- **Effort / impact:** M (3 h) / every role decision consistent and explainable.
- **Verdict:** improve.

### 1. Intake (deep)
- **In / out:** chips, chat box, worker buttons, worker chat, expert toggle -> text or metric ids.
- **Now:** steward_app.py `CHIPS`, `ask()`; worker.py `PROMPTS`, `words_to_metrics`.
- **Assumption:** each population needs its own entry point. True: Panu says floor = find fast, builder = maintain.
- **Attack:**
  - The **expert toggle is a second pipeline**, not a density setting: the same question gives a different verdict
    (below).
  - Chips are fixed strings, not built from the user's role or plant.
- **Optimise:** one entry pipeline; "expert" changes only how much is shown. Chips generated from the user's
  department -> KPI map (steward/departments.py already exists).
- **0 to 1:** the first screen already answers. On login, run the user's department KPIs through the chain and show
  "Your 3 numbers today": reuse-only, zero questions, zero LLM calls.
- **Verdict:** improve.

### 2. Understanding (deep)
- **In / out:** text -> `ParsedQuestion` (expert) or `Intent` (novice).
- **Now:**
  - Rules: query_parser.py (dictionary match).
  - LLM: interview `_llm_intent`, plus `_ask_ai` in expert mode.
  - Glue: `intent_from_parsed` and `to_parsed_question` convert between the two.
- **Assumption:** the parser was there first, the Intent was added for the interview, an adapter joins them.
- **Attack:**
  - **Expert vs interview, 30 labelled rows:** they disagree on 19.
  - **Same request, two verdicts:** "Is supply safe for Plant-B?" -> expert CLARIFY ("Not in the governed dictionary:
    'supply', 'safe', 'Plant'"), novice CREATE.
  - **Rules parser CLARIFY rate:** 91/150 data-pack requests (61%). The themes that understand "supply safe" live
    only in the interview.
  - **Ids vs names:** see F1.
  - **Contradictions are swallowed:** "Show me Eylea in Japan, but not Japan, worldwide" -> interview with defaults
    picks JP, no conflict raised, EXTEND.
- **Optimise:**
  - **One understanding function** -> one `Intent` with ids only (names only for display). The rules parser and
    the themes become its offline fallback.
  - Delete `to_parsed_question`: let `decide` take the Intent directly, or at least map names -> ids in one tested
    place.
- **0 to 1:** an **Intent receipt**: every field shows where it came from (said by the user / login profile /
  theme / default / AI) and its confidence. It is the input and output of step 2 that Panu asked to see.
- **Effort / impact:** F1 fix S (1 h incl. a test that runs the labelled set through the interview path); merging
  the paths M-L.
- **Verdict:** replace the adapter.

### 3. Grill-me (deep)
- **In / out:** text + replies -> confirmed Intent; up to `MAX_QUESTIONS` 5, early stop on confidence.
- **Now:** interview.py (646 lines), prompts/interview.yaml (209 lines); one LLM call per turn (`_llm_intent`).
- **Assumption:** ask until the Intent's confidence fields pass `CONFIDENCE_MIN`.
- **Attack:**
  - **It asks questions whose answer changes nothing.** For REQ-0001 and "Xarelto net sales in Germany" the only
    question is "Last question: what is this for?". `decision_supported` feeds only the LLM layout prompt
    (layout.py:233) and spec metadata (specbuild.py:469). In rules mode every answer gives the same verdict, spec
    and page.
  - **Confidence is per field, not per decision.** The interview asks to fill fields, not to resolve what actually
    splits the outcome.
  - **Not role-aware:** management and builder get the same questions; plant and department from the login are
    never used.
  - **Costs one LLM call per turn** (Margiris measured ~25 s per Aitta call). Five turns = minutes before the first
    pixel of a dashboard.
- **Optimise:**
  - Prefill from the login (plant -> site, department -> KPI set). Several questions disappear.
  - Never ask a question whose options all lead to the same verdict and spec.
- **0 to 1: a value-of-information interview.**
  - For each open field, run its candidate answers through search + decide. In rules mode that takes 16-34 ms each,
    so all options cost well under a second.
  - Ask only the question whose answer splits the outcome most (e.g. "Germany only -> REUSE AST-0191; all of
    Europe -> EXTEND AST-0042").
  - Stop when no answer can change the verdict.
  - Show the options **with their consequence**: "Germany only (an existing report answers this now)".
  - The result: short by construction (Panu point 1), provably minimal, and every question is visibly worth asking.
    No other team will have this.
- **Effort / impact:** M (3-4 h on top of the F1 fix) / fewer questions, every question explainable.
- **Verdict:** replace the stopping rule.

### 4. Search (brief)
- **Now:** BM25 + trigram + embeddings (off without Gemini) + structure, fused by RRF, top-40 -> decide.
- **Attack:**
  - F2: the cutoff drops extendable assets (26/150).
  - Search docs still say "questions are often in Russian" (engine.py:43): inherited from the original repo.
- **Optimise:** decide on KPI coverage over **all** assets (360 assets, 34 ms). Keep text search only to rank ties,
  and for requests with no governed KPI ("our Tableau Xarelto workbook").
- **0 to 1:** a coverage index (KPI id -> assets) makes the candidate set exact and explainable: "these 7 assets
  carry 2 of your 3 KPIs".
- **Verdict:** replace the cutoff.

### 5. Decision (brief)
- **Now:** rules engine, coverage thresholds (REUSE 1.0 / EXTEND 0.5), lifecycle flags. Verdict in code: right, keep.
- **Attack:**
  - Site scope changes the verdict for no data reason: "Is supply safe?" -> EXTEND, "...for Plant-B?" -> CREATE.
    The site is a data filter (pipeline.py:200), but the empty product/market filters behave differently from the
    "All Pharma/Global" defaults.
  - Estate on the interview path: 111 EXTEND / 39 CREATE / **0 REUSE**.
- **Verdict:** keep, fix the scope inputs.

### 6. Explanation (deep)
- **Now:** four narrative layers for one decision:
  1. explain.py (template or LLM, "Full explanation");
  2. investigate.py (AI trail);
  3. takeaway.py (lead sentence above the tiles, its own LLM call per spec and filter);
  4. `why_sentences` and `verdict_reason` (code).
- **Attack:**
  - Overlapping text, up to 3 LLM calls per request (explain, investigate, takeaway), the first two sequential on
    the novice path.
  - A novice sees headline + verdict reason + lead + Why: four ways of saying the same thing.
- **Optimise:** one structured call after the decision returns `{headline, why[<=3], takeaway, trail}`, and code
  checks every number. Or code-only for the novice and the trail only for the BI team.
- **0 to 1:** the **ruling as a document**: every sentence footnoted to the record id or rule that proves it. A
  sentence without proof is not shown.
- **Verdict:** merge.

### 7. Data and semantics (brief)
- semantic.profile + check_visual (Martynas) are good; they now gate the layout menu (8fe651b).
- **Attack:** feasibility gaps (KPI-034, KPI-039) only surface after the verdict. The interview could say "this
  number is not governed yet" before asking anything else.

### 8. Spec and layout (deep)
- **Now:** specbuild template (4 cards, trend, bar, table) -> LLM reorders inside a role envelope -> code validates.
- **Assumption:** "dynamic" = an LLM reorders a menu.
- **Attack:**
  - **The LLM adds one more call to change the order of 4-7 items.** In rules mode the page is the same template
    for every question.
  - The hierarchy is not driven by the data. A KPI 20% off forecast and one exactly on target get the same slot.
- **Optimise / 0 to 1: data-first hierarchy, deterministic.**
  - Rank visuals by what the data says: breach of a governed threshold, size of the deviation vs forecast or prior,
    trend break, exceptions count.
  - The most off-target KPI leads; a calm KPI shrinks; the exceptions table appears only if it has rows.
  - The role sets the depth (envelope). The LLM writes only the one-line subtitle question, or nothing.
  - Instant, offline, explainable ("leads because 18% under forecast"), and actually personalised to the data. This
    is what Panu's "make it dynamic" meant (transcript: "it still uses the same charts").
- **Effort / impact:** M (3 h; profile, check_visual and the thresholds exist) / the dashboard visibly reacts to
  the data.
- **Verdict:** replace the LLM ordering with data ranking; keep the role envelope and the validation.

### 9-15. Brief

| Node | Observation | Verdict |
|---|---|---|
| 9 Lint | In the traces it blocks only for RULE-005 (Eylea JP, failing refresh). It never vetoes a layout. Fine. | keep |
| 10 Render / UI | Same page for every verdict except gaps. Charts colour-coded in render.py (Donatas). Not deep-checked by me. | Donatas |
| 11 Governance | Journal and requests are per-process files plus session state. No cross-user queue. | improve |
| 12 PBIP | Verified in Desktop for REQ-0001 only (Martynas M4). Role layouts are not exported. | Martynas |
| 13 Health | Retire funnel and owners match the data pack. Not tied to "my assets" per builder (Panu point 6, open). | improve |
| 14 Proof | **Measures only the expert path** (F1 survived because of this). golden_questions.json still holds sample crop-science cases. | fix first |
| 15 LLM infra | Novice path: (turns) interview calls + explain + investigate + layout + takeaway = 5 calls at 2 turns, sequential. Expert ask: 3. Disk cache for layout only (8fe651b) and backend replay. | cut calls |

## End to end per role (rules mode)

| Request | Builder | Management | Worker |
|---|---|---|---|
| LATAM this quarter | EXTEND, 6 visuals, 409 ms | same | EXTEND, 4 visuals, OTIF hidden (labelled) |
| Supply safe Plant-B | **CREATE** (expert: CLARIFY) | CREATE | CREATE |
| Xarelto DE | **CREATE (should be REUSE AST-0191)** | CREATE | CREATE |
| REQ-0001 Nubeqa | EXTEND, 7 visuals | EXTEND, 6 | EXTEND, 4, Market Access hidden |
| My plant efficiency | EXTEND, asks "which site" first | EXTEND (own plant after 0903371) | EXTEND |
| Eylea JP / not JP | EXTEND, contradiction missed, RULE-005 block | same | same |

- **Speed:** every step after understanding is under 0.6 s offline. Latency is entirely LLM calls (4-8 per novice
  request).
- **Worker:** its own reuse-only path (worker.py) never goes through the interview, so F1 does not affect it.

## Top 3 changes
1. **One understanding pipeline with ids, measured** (F1 + the adapter + the eval on the novice path).
   - Map names -> ids once; run the labelled set through the interview path in eval_steward.py; one Intent for
     expert and novice.
   - Effect: restores REUSE on the main path (3/9 -> 7/9) and ends "same question, two verdicts".
   - S for the fix, M for the merge.
2. **Decide over the full KPI coverage index, not the top-40 text hits** (F2).
   - Effect: removes 26/150 false CREATEs. ~18 ms extra.
   - S.
3. **Value-of-information grill-me + data-first layout.**
   - The interview asks only what changes the outcome (computed by running the options through decide), prefilled
     from the login.
   - The dashboard's hierarchy comes from the data's deviations.
   - Fewer questions, fewer LLM calls, both explainable. M.

Also: fix F3 now (`make demo` must load the data pack). That is a one-line change and the demo depends on it.

## One bold idea: the chain proves itself
Every step emits a one-line **receipt**: input -> output -> why -> what it cost (ms, LLM calls). Examples:
- "understood: Xarelto, DE, Net Sales (said); site Plant-B (login)"
- "searched 360 assets, 7 carry Net Sales"
- "AST-0191 covers 100% -> REUSE (rule REUSE_MIN_COVERAGE)"
- "layout: Net Sales leads, 12% under forecast"

The receipts render as a vertical strip beside the result (the BI team's details) and as the pitch slide. That is
literally Panu's point 8 (logical sequence, inputs and outputs per step), produced by the product itself, and true
for every request a judge types.

## More ideas (rule 18:50: at least 5 optimisations + 3 bold ideas beyond the top 3)

### Optimisations
- **O1. Rules first, LLM only when unsure.** The themes and the dictionary already understand every chip and most
  floor questions. Call the LLM for understanding only when rules confidence is below the threshold. Common
  questions then cost 0 LLM calls; today each interview turn costs one.
- **O2. Fan out after the decision.** explain, investigate, layout and takeaway depend only on the decision and the
  spec, not on each other. Run them in parallel (today the novice path runs them one after another). Latency drops
  to the slowest single call.
- **O3. Speculative results.** The value-of-information interview already runs every option through decide. Keep
  those results: when the user taps an option, the ruling and the dashboard appear at once, with no wait after the
  last answer.
- **O4. Disk cache for understanding, like the layout cache.** Key = normalised text + the user's profile. The
  warm script fills it for the demo questions, so every demo question is instant and immune to 429s, including
  understanding.
- **O5. Memoise the data work per scope.** semantic.profile, compute and feasibility for the same
  (measures, filters) run again on every build and every Streamlit rerun. One `lru_cache` keyed by the spec hash.
- **O6. Delete what we no longer run:**
  - the invented sample catalog (makes F3 impossible);
  - tests/bi_steward/golden_questions.json (crop science, out of scope);
  - the legacy backend/ pipeline and frontend/app.py, which the pre-push suite still tests.
  Fewer paths to keep consistent, and a faster pre-push (about 90 s today).

### Bold ideas
- **B1. The counterfactual ruling.** Every EXTEND or CREATE also says what would have made it a REUSE: "If AST-0191
  carried Forecast Bias, this request would be answered by an existing report." Code computes it from the coverage
  gap. It turns every request into a precise maintenance ticket for the asset's owner: the builder's view Panu asked
  for (point 6), generated by demand.
- **B2. The demand ledger.** Every request, REUSE included, is logged as demand: KPI x scope x role. Builders see
  "14 people asked for Net Sales in DE this month, AST-0191 answers them". Retire, extend and certify priorities then
  come from real demand, not only from usage logs. It links the request flow to estate health, the two halves of
  the challenge.
- **B3. A catalog that learns, governed.** When a request phrased in new words is approved as REUSE of an asset, the
  wording is proposed as a synonym on that asset. The asset owner approves it, and it is journalled like any change.
  Search gets better with use, and every change to it stays governed.
- **B4. Replay the estate in front of the judge.** One button runs all 150 Bayer requests through the live chain and
  shows the funnel: reused / extended / created / clarified, dashboards avoided, KPI conflicts caught, owners
  missing. That is quantitative proof without a pilot (Panu: "quantitative is hard"), and the judge can rerun it.
- **B5. Dashboards with history.** The spec hash plus the journal already form a version chain per asset. Show it as
  a diff between version n and n+1 (KPIs added, a variant swapped, owner changed), with rollback. Builders maintain
  assets the way developers maintain code.
