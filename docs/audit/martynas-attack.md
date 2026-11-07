# Attack (phase 2): Martynas's Claude, Sat 7 Nov

Attacks `gajus.md` (+ the follow-up O1-O6 / B1-B5), `gajus-chain.md`, `margiris.md`, `donatas.md`. Read after my own audit was pushed (0e20c10).
Rule used: **agree = one line, disagree = why + evidence + a better alternative, combine = say what the mix is.** Anything I could not verify is marked.

## 0. New evidence I produced for this round (so the attacks below are not opinion)

**Experiment: independent probes.** I generated 980 probes (7 products x 14 markets x 10 bindable KPIs, e.g. "Hyrnuo inventory coverage in China") and computed the correct answer **from the data pack with BUILD_PLAN rules, not from the engine**: a Power BI asset, product in {P, All Pharma}, market in {M, Global}, the KPI as a **canonical** id, trust >= 0.6 (with the BUILD_PLAN 2.3 rule "inactive owner, role still staffed = 0.10"). Then I ran the real engine (rules mode, original pack) on 80 of them (40 with a covering asset, 40 without) through both paths: `ask` (expert) and `ask_intent(intent_from_parsed(..))` (what the interview/AI uses).

| Probes with a covering asset (n=40) | REUSE | EXTEND | CREATE (**false**) |
|---|---|---|---|
| expert path, search top-40 | 25 | 12 | 3 |
| Intent path, search top-40 | 21 | 4 | **15** |
| expert path, search = all 360 assets | 28 | 12 | 0 |
| Intent path, search = all 360 assets | **32** | 4 | 4 |

- **False REUSE on the 40 probes with no covering asset: 0 on every path.** The engine is safe; its failures are all in the "build less" direction (false CREATE / EXTEND).
- Gajus's F1 + F2 are real and measured on data I did not tune on: the Intent path loses 15/40 to false CREATE; widening search alone recovers 11 of those; residual 4 are F1.
- **New (B1): the REUSE check only looks at the single best-scored candidate.** 12 of 40 covered probes stay EXTEND even with the full scan. Example: "Hyrnuo inventory coverage in China": best = AST-0024 (coverage 1.0, trust **0.55**, score 0.865); second = AST-0335 (coverage 1.0, trust **0.60**, score 0.839). `engine.py:~163` takes `best = eligible[0]` by `0.6*coverage + 0.3*trust + 0.1*search`, then tests `trust >= 0.6` on that one only. A REUSE-eligible asset in second place is ignored. Fix: choose the best among candidates that pass the REUSE gates first, fall back to the blended score only if none pass. S, 15 min, `steward/decision/engine.py`.
- **New (B2): one weak asset carries the REUSE story.** With the corrected trust, **54% (233 of 434)** of the REUSE-eligible probes are served *only* by AST-0335 "All Pharma Growth Legacy" (promoted, owner inactive, 0.5 users/month, refresh ok, and the estate flags it RETIRE). It alone makes Net Sales, Inventory Coverage and Market Access "reusable" for every product in every country. Eligible share: 44% lenient, 39% if endorsement is required, **10.6%** if endorsement + active owner + healthy refresh are all required (Margiris's gate).
- **Period readings differ 10x** (LATAM Net Sales, Nov 7): calendar quarter-to-date (Oct only) 249.1; last full quarter (Q3) 656.6; last 3 months 692.0; all months 2,431.4. Donatas's 2,431.4 vs 692.0 reproduces exactly.
- Request texts: 150 requests, **10 distinct texts**, and **no requester column** in `Business_Requests` (columns: request_id, request_date, product_context, market_context, request_text, urgency, status).

I checked and **retract** one suspicion of my own: I thought four `read_excel(DEFAULT_XLSX)` call sites ignored the large pack; they follow `STEWARD_DATAPACK_XLSX` (`datapack.py:27`). Not a bug. (They are still 7 separate `read_excel` call sites in `steward/`, several of them re-reading the same workbook.)

---

## 1. Gajus (`gajus.md`, follow-up, `gajus-chain.md`)

**Agree (one line each)**
- F1 names vs ids: agree, now with a number: 15/40 false CREATE on the Intent path (section 0).
- F2 decide over the full coverage index: agree; 0 false REUSE with full scan on my 80 probes, REUSE on the Intent path 21 -> 32.
- F3 `make demo` loads the 19-asset sample: agree (Makefile `demo:` has no `STEWARD_CATALOG`); I hit it myself (my first trace returned CLARIFY on everything).
- Eval measures only the expert path (node 14): agree; Margiris proposes the fix.
- Intent receipt, per-step receipts, ruling-as-document, one understanding function: agree.
- C1-C10 connectors: agree; C9 (floor request re-sent as text) and C10 (hard-coded `LACKS`) are cheap and right. C8: confirmed, 7 `read_excel` call sites in `steward/` (`datapack`, `lifecycle`, `requests` x2, `semantic` x2, `specbuild`).
- Z5 KPI type checker and C7: **numbers reproduce exactly** (Plant-A inventory 6.92 vs 7.60 weeks, Plant-B OTIF 78.26 vs 77.05, Plant-C 6.24 vs 6.86 / 83.35 vs 82.45). Agree on the idea; effort below.
- Z6 governed answers API: agree; my vote for the pitch idea (see below).

**Disagree / refine**

1. **Data-first layout ("the most off-target KPI leads") is under-specified.** *Evidence:* a deviation needs a target and a common scale. Only 3 of the 12 bindable KPIs have any threshold (`specbuild.py:32` EXCEPTIONS: KPI-042, KPI-020, KPI-016); the rest have none; units differ (EUR, %, weeks, units, index), so "20% off" is not comparable across them; snapshot KPIs (006, 031, 054) have no prior period. *Better, deterministic and buildable now:* two-key order: (1) the governed `business_criticality` from `KPI_Catalog` (9 of the 12 are *high*, 3 *medium*), (2) signed deviation vs the comparator where one exists (prior month for monthly KPIs, forecast for KPI-001/042), (3) KPIs with no comparator keep template order. "Leads because: high criticality, 14% under prior month." Targets for the other 9 become a roadmap item, not a prerequisite. The PBIP already follows `Visual.step` (c28331a), so it exports for free. S-M, 2 h.
2. **O6 "delete legacy backend/" would break the LLM path.** *Evidence:* `steward/llm.py:87-88` imports `backend.llm` and `backend.config`; `steward/config.py:16` imports `backend.config`; `frontend/steward_app.py:137` imports `backend.llm`. *Alternative:* delete `backend/pipeline.py`, `backend/main.py`, `backend/ingest.py`, `backend/audit.py`, `frontend/app.py` and the tests that pin them; keep `backend/llm.py` + `backend/config.py` until they are moved into `steward/`. Delete the sample catalog and `golden_questions.json` only with a replacement contract, since CLAUDE.md calls the goldens "the verdict contract".
3. **Rank 6 "weighted aggregation, S, 1 h" is M, ~3 h and needs an ESCALATE.** *Why:* it changes governed numbers on every card (Nubeqa Market Access 66.38 -> 65.44) so `pbip_open.png` and any pitch number must be redone; the **weight is a definition** (inventory weeks by units shipped, or by net sales? OTIF by units?), i.e. a KPI-definition decision, not a code detail; three DAX measures become `SUMX`/`DIVIDE` and must be re-verified in Desktop (my 12-card check export is the test); `test_semantic.py` compares `compute` with raw simple means and `test_pbip.py` asserts the `AVERAGE` form, so both change. Do it, but schedule it as M and decide the weights first.
4. **Rank 2 "Period is first-class, S" is M and needs a definition.** Four readings of "this quarter" span 249.1 to 2,431.4 (section 0). Needs `Intent.period` (a contract), parser words (`quarter`, `YTD`, `last month`), `spec.filters`, a label on every card, and my calendar columns in the model. *Recommendation:* escalate one rule, e.g. "this quarter = the last 3 complete months, printed on the card", rather than guessing per request.
5. **Z1 earned permanence: right story, wrong trigger.** *Evidence:* "N distinct *people*" cannot be computed: the pack has no requester column and the demo has 4 accounts. The pack does support "N distinct *requests*": 10 distinct texts, each in 5+ requests. *Alternative trigger:* intent signature repeated by N distinct request ids (or sessions). Also: a minted asset still needs an owner (RULE-003) and a sunset shown on the card, or a worker's view that vanishes after 30 days will look like a bug. M, 3 h, touches governance, journal, catalog and search; roadmap unless nothing else is as strong.
6. **Z2 carrying cost: do not invent units.** "~X maintenance hours, budget 120, used 113" has no source; a judge will ask where 120 comes from. *The pack has real inputs:* `Semantic_Models.table_count`, `measure_count`, `refresh_frequency`, `ai_readiness`. *Alternative:* a labelled **maintenance load index** = tables + measures of the model the asset depends on, per asset sharing it, shown as "retiring AST-X frees N tables / M measures". No budget, no hours.
7. **Z4 benchmark without access leaks.** *Evidence:* `auth.py` docstring: workers see "Other plants: never directly, only what their manager shares." "3rd of 10, best is 91%" reveals the best plant's value and the worker's rank; a minimum group size of 5 does not stop that. *Alternative:* compare the worker's number with the **company band** (median and P25-P75 over >= 5 plants) or with their own previous month. No single other plant's value is disclosed.
8. **Z6 needs the same policy as the UI.** An API that returns `answer(kpi, scope, period)` bypasses worker plant scoping unless it calls `can_see`/the policy table. State this and put the policy table (Gajus node 0) *under* both. Mock login is not auth; label it.
9. **Value-of-information interview: right, but gated.** It runs every option through `decide`; with F1 unfixed every option returns CREATE and it would ask nothing useful. Order: F1 + F2 + B1 first, then VOI.

**Combine**
- Receipts (his, per step) + my **"show your work"** (per number): one `Receipt` record `{step, in, out, why, ms, llm_calls, dq, rows_used}`; the strip shows steps, the number's click-through shows the compute record. One structure, two views.
- Z6 + my number lineage: the API response carries `{value, kpi, dax, rows, dq_notes, owner, spec_hash}`. That is the "governed answer with provenance".

---

## 2. Margiris (`margiris.md`)

**Agree**
- `existing_answers(intent)` as the one function for engine, worker and lint: agree, top change. **Add scope to it:** scope normalisation lives in four places (`signals.coverage`, `lint._scope`, `semantic._scope`, `auth.can_see`), one correct per her finding.
- RULE-001 uses Jaccard so a CREATE passes lint while AST-0191 covers 100%: agree; containment is the right test.
- FALSE-CREATE metric + recall probes + honest sample sizes: agree and **I can supply the generator** (below). 10 distinct request texts: confirmed.
- DEMO_MODE must cover text calls; deterministic JSON on every provider; tests 164 s -> under a minute; negatives in AI mode; lint block rate as an eval number: agree, all S.
- "Drop and show" instead of STOPWORDS whack-a-mole: agree, with one rule: **`quarter`, `month`, `YTD` are period words, never "dropped"**; they must map to `Intent.period` or be listed in Donatas's "not applied" list. Drop-and-show and Donatas's RULE-ANSWER need to share that list.
- Disagreement as a free hold-out and the governance fuzzer: agree (below).

**Disagree / refine**

1. **"REUSE needs endorsement" as a verdict gate removes most REUSE, and one asset decides the rest.** *Evidence (section 0):* eligible probes 44% lenient -> 39% endorsed -> **10.6%** with endorsed + active owner + healthy refresh; 54% of the lenient eligibility is AST-0335 alone. The gate is *correct* about that asset (inactive owner, 0.5 users/month, RETIRE-flagged), but as a hard verdict change the demo shows almost no REUSE. *Alternative:* keep the verdict taxonomy; make the gates a **ranking key** ("lifecycle before choice": healthy, endorsed, owner-active assets rank first, so a healthy REUSE wins when one exists) and print the failing gates as the existing flags (`REASSIGN_OWNER`, `FIX_REFRESH`, RETIRE) on the card. Whether endorsement is a hard REUSE condition stays Gajus's call (it is a threshold). *Hold-out:* H-25 stays labelled REUSE until the rule changes; per BUILD_PLAN 12 a rule change moves the label in the same commit.
2. **Net-zero estate as a gate would deadlock.** *Evidence:* the estate has **21** retire candidates in total (funnel 360 -> 354 -> 74 -> 62 -> 21 -> 21), each needing age >= 3 months, low use and no dependants (BUILD_PLAN 2.2). A rule "no approval without a matching retirement" would stop after 21 approvals, and forcing a retirement would break the "quiet" criteria. *Alternative:* net-zero as a **meter and a default**: the approval card shows "+1 dashboard, -N retirable (list)", and a net-positive approval needs a one-line justification in the journal. Combine with Donatas's build-less meter.
3. **Disagreement as hold-out: keep the labels separate.** A builder's pick under time pressure is not the same as a hand label made before tuning. Store them as `source: live-disagreement`, report them in their own column, never in the headline accuracy.

**Combine**
- **Probe generator for her FALSE-CREATE / recall item.** My method (section 0) is data-derived, independent of the engine, and already run: 980 probes, ground truth from the pack. Proposal: commit it as `data/build_probes.py` (mine, S, 1 h) and let `eval_steward.py` score it on both paths and report false-CREATE, false-REUSE, recall. This is her fuzzer's "correct outcome known by construction" idea, applied to the REUSE side. Her adversarial generators (variant KPI names, contradictions, injections) then sit next to it.
- **B1 (shadowing) + her "lifecycle before choice" are one change** in `engine.py`: select the best among candidates that pass the REUSE gates, ordered by (gates passed, then score). Two audits, one fix.

---

## 3. Donatas (`donatas.md`)

**Agree**
- TL;DR 1 (F1 confirmed through the LLM-outage path): agree; the 429 fallback goes through the same adapter.
- TL;DR 2 period silently dropped: agree, **numbers reproduce** (2,431.4 vs 692.0); I add the definition problem (section 1, item 4).
- TL;DR 3 approvals poison later verdicts: agree; I also saw AST-0335 carry the REUSE story (B2), so a stale extension of that asset would move many answers.
- TL;DR 5 owner accepts anything: **confirmed in code**, `governance.py:48-49` only checks `if not owner`; no lookup in Owners.
- Ordered `RenderedDashboard` blocks: agree; PBIP already orders by `Visual.step`, so after this the render and the export match. I will add a test that render order == PBIP `tabOrder`.
- LLM circuit breaker, layout memo, hash-chained journal, send-back reaches requester, permission check inside `approve`: agree, all S.
- EXTEND forbidden on legacy / retire-candidate assets: agree; it is the same fix as Margiris's lifecycle-before-choice (one change, not two).

**Disagree / refine**
1. **"This changed" push needs history the data does not have.** *Evidence:* the facts are monthly, Jan-Oct 2026; there is no "since your last visit" in a static pack (as_of 7 Nov). *Alternative:* "crossed a threshold **since the previous month**", which the data supports. Thresholds exist for only 3 KPIs (OTIF < 90, inventory < 4 weeks, forecast variance > 10%), which is enough for a demo; say that out loud.
2. **Tone from KPI direction (`better_is`) is necessary but not sufficient** for Gajus's data-first layout: direction without a target still cannot rank unlike KPIs (section 1, item 1). Keep it; do not claim it solves ranking.
3. **"Approval is a contract that re-checks itself"** is the best idea in the set; its risk is cost of replay on a large estate. *Evidence:* the spec build is 0.1 s on the large pack, but loading the pack is 46 s (two full reads); replay must reuse the already-loaded frames, so the cache of the parsed pack is a prerequisite.

**Combine**
- **Replay + PBIP stamp = both halves of one loop.** Donatas's replay catches "the catalog changed since approval". My PBIP idea catches "the file in the wild is not what was approved". Make them one record: the journal stores `{decision hash, promised numbers, view hashes}`; replay diffs the journal against today's data; the exported PBIP carries the decision hash as a model annotation so any `.pbip` can be matched back to its approval (and its measures diffed against `measures.json`). One mechanism, estate-wide and file-level.
- **Shadow the requester + my S2 (three spec hashes per request):** the journal stores the decision hash once and one view hash per role; maker/checker then sees exactly what each viewer will get.

---

## 4. A merged ranking, to help DECISION.md (not a decision)

| # | Change | Combines | Effort | Why this order |
|---|---|---|---|---|
| 1 | Ids in the Intent path + search over all assets + **pick the best among REUSE-eligible first** | Gajus F1, F2, my B1, Margiris lifecycle-before-choice, Donatas "no EXTEND on legacy" | S-M, 2-3 h, one PR across intent/decision | Measured: Intent path 21 -> 32 of 40 REUSE, false CREATE 15 -> 4, with the shadow fix more; 0 false REUSE |
| 2 | `existing_answers()` for engine, worker, lint + one scope function | Margiris top 1 | M, 2 h | Removes three disagreeing definitions and the lint-passes-a-duplicate case |
| 3 | Probe generator + FALSE-CREATE metric + Intent-path eval | Margiris top 2, my probes | S, 1-2 h | Makes 1 and 2 measurable and protects them from regression |
| 4 | Period as a first-class field with **one escalated definition** | Donatas top 1, Gajus rank 2, my calendar columns | M, 3 h | 10x spread on the commonest floor phrase |
| 5 | Governance write side: owner pick-list, no self-poisoning, seeded demo dir | Donatas top 2, Gajus C3 | S-M, 2 h | Stage reliability and Panu point 9 |
| 6 | Cache the parsed pack, fix the quadratic scan, 12 measures verified in Desktop | my top 1-2 | S, 3 h | 46 s -> seconds; 8 of 12 KPIs are unverified on stage |
| 7 | Weighted/typed aggregation for 3 KPIs, weights decided first | Gajus Z5 + C7, my A3 | M, 3 h | Correctness; schedule after 1-3 |
| 8 | Decision hash + replay + PBIP stamp | Donatas bold, my round trip | M, 3-4 h | The "governed loop" story; roadmap if time is short |

**Pitch idea:** Z6 (governed answers API with provenance) is my vote for the single new idea: cheapest to show (FastAPI already exists in `backend/main.py`), strongest "why this matters next year", and it carries the provenance record from the number lineage. Z1 earned permanence is the best "build less" roadmap line. What I would *not* do before the freeze: Z2/Z3/Z4 (each needs UI, state or an invented unit), the VOI interview rewrite before 1-3 land, the nightly replay (8) unless 6 is done.

## 5. What I am changing in my own audit after reading the others
- My A3 (unweighted means) was under-weighted: Gajus's per-plant table shows up to a 10% gap (Plant-A inventory), not the <1 point I saw on Nubeqa. Agree it is a correctness issue; effort corrected above.
- My top-3 #3 (period in the model) stays as the model-side half of Donatas's period fix, behind the definition decision.
- I would add B1 (REUSE shadowing) and B2 (AST-0335 carries 54% of REUSE eligibility) to my findings; they came from this round's probes, not from the first pass.
