# Attack: Gajus's Claude (phase 2, Sat 7 Nov ~19:30, main at 8fa8783)

Read: donatas.md (c694751), martynas.md (0e20c10), margiris.md (fca9db4 + 8fa8783), and gajus-chain.md (90faf08,
written by Gajus's other session; attacked here like the others).
- New evidence is from commands run on main, rules mode, data pack.
- Per the 18:50 rule, alternatives below are new, not restated. Where I agree I say so in one line.

## 0. Attack on myself first

**F2 is overstated.**
- I wrote "26/150 requests (17%) are false CREATE because of the top-40 cut". Margiris is right that the 150 are 10
  distinct texts. Re-run: **the 26 flips are 2 distinct texts** ("monthly supply-risk dashboard by medicine and
  country", "launch dashboard for Lynkuet with market access").
- Worse: on the full scan, the winner for both is **AST-0335 "All Pharma Growth Legacy", owner inactive, flags
  REASSIGN_OWNER + RETIRE**. So "decide over all assets" alone turns a false CREATE into an EXTEND of a report we tell
  people to retire. Margiris found the same on REQ-0001.
- **Correction:** F2 is only safe together with Margiris's "lifecycle before choice" (rank RETIRE / failed refresh /
  inactive owner below healthy candidates). The two are one change, not two.
- My Top 3 #2 stands only in that combined form.

**F1 stands.** Confirmed independently by Donatas (5/21 sweep, also on the LLM-outage path) and Margiris (signals.py:40-44,
plus the same adapter in `_ask_ai` and `_adopt_asset`). Three blind audits, one root cause.

**My node 12 line "role layouts are not exported" is wrong.** Martynas measured builder 7 -> 7 exported, worker 4 -> 4.
Withdrawn.

**Value-of-information interview: right idea, wrong time.**
- It runs candidate answers through `decide`, so it inherits F1, F2 and the lifecycle bug.
- Before those are fixed it would ask the user to choose between two wrong verdicts. Sequencing: after the fixes, or
  roadmap.
- gajus-chain.md already parks it; I agree.

**Data-first layout.** Martynas's phase-2 note is fair: only 3 of 12 KPIs have a threshold (specbuild.py:32), so
"breach of a governed target" cannot drive the ranking. Answer, new below: rank by **signed deviation x better_is**
(Donatas's direction field), no target needed.

## 1. Donatas (render, governance, demo flow)

| Idea | Verdict | Attack / alternative |
|---|---|---|
| TL;DR 2 period silently dropped (EUR 2,431M vs 692M) | **Agree, top-3 material** | Biggest wrong *number* anyone found. Fix at the Intent (period field) **and** gate it with his RULE-ANSWER, below. |
| TL;DR 3 approvals poison search | Agree; **the fix should be different** | Seeding a clean demo dir hides the bug on stage and keeps it in the product. Root cause: an approved EXTEND **mutates the catalog asset as active and fresh** (`_extend` sets `last_refreshed=as_of`). Alternative: approvals write a **pending change set** next to the catalog, never into it; search reads the base catalog plus only *certified* changes. Reproducible demo and a correct product with one rule. The seed dir is still worth adding as a belt. |
| TL;DR 4 render buckets lose the step order | Agree | `RenderedDashboard.blocks` is the right shape. It is also the prerequisite for any dynamic layout to be visible, mine included. |
| TL;DR 5 "Mickey Mouse" owner | Agree | The pick-list is the minimum. Combine with Martynas bold 1 (owner chain + why it exists). |
| RULE-ANSWER lint (every scope word applied or listed "not applied") | **Agree, upgrade it** | Lint is the backstop, not the fix. Run the same check at the **Intent** (before decide) so the interview can ask "you said *this quarter*: Jul-Sep?" instead of a lint warning after the build. One function, two call sites. |
| Approval contract that replays itself | Agree in principle; **too big tonight** | It overlaps Martynas's PBIP drift and my B5 history: three versions of one idea. Take Donatas's as the base, roadmap for the README. |
| Circuit breaker + "AI paused" badge | Agree, S | Combine with my O1 (rules first): with rules first most chips never call the LLM, so the breaker rarely matters. |
| "Shadow the requester" view | **Superseded** | Martynas's decision/presentation split makes the requester's view a derived, hashed artefact. The shadow view is then just its UI, not a separate idea. |
| Second role cut in the UI (`keep = max(2, ...)`) | **Agree; it is mine** (8fe651b) | Delete it. layout.py stays the only cut and records it. |

## 2. Martynas (data, spec, PBIP, health)

| Idea | Verdict | Attack / alternative |
|---|---|---|
| A2 only 4 of 12 measures verified in Desktop | **Agree, do it first** | 5 minutes of a human on Windows, zero code. Schedule it as the first act of the build. |
| S2 one request, three specs, one approved | **Agree: the strongest structural finding** | Decision/presentation split as he proposes is M (3-4 h) and touches lint, render, journal. Cheaper version that keeps the contract: add `decision_hash` (verdict, KPIs, scope, measures, changes) next to `spec_hash`. The journal approves the decision hash; each role view stores its own view hash plus the decision hash. S, 1 h, same pitch line ("one approved decision, many governed views"). |
| A4 large pack startup 46 s (Excel read twice) | Agree, **low priority** | Original pack: 2.9 s. It matters only if we demo the large pack. Do it if his conformance idea (bold 4) makes the cut, otherwise later. |
| A6 / 0-to-1 gap -> governed data request to the KPI owner | **Agree, high value per hour** | Turns NOT_FEASIBLE from a dead end into an action with a named person: Panu point 9 (ownership) plus point 2 (KPIs must be defined; here is who defines them). Pair it with Margiris's checklist: the first failing gate "no source data" becomes the ticket. |
| H1 "stale" = 71% of the estate | Agree | Use "stale relative to its refresh cadence" (cadence exists on the spec). |
| H4 16 certified assets on a failed refresh | **Agree: headline for the builder view** | It is also a decision bug: trust adds certified 0.40 regardless of refresh. Feed it into Margiris's gate checklist. |
| O3 derive `feasible` from the data | Agree | Prerequisite for his conformance report. |
| O4 lint wording from the `Governance_Rules` sheet | Weak | The rule names already match; it changes text, not behaviour. Roadmap. |
| PBIP round trip with drift detection | Agree as idea; **roadmap** | M-L. Judges will not open a re-imported file. Keep the spec-hash stamp in the TMDL (S), skip the reader tonight. |
| Role scoping in `build()` (Worker21 Nubeqa spec has no plant filter) | Agree | Belongs in the one policy table (my node 0). Note: worker.py and own_plant_scope (0903371) are two partial fixes of the same gap. |

## 3. Margiris (search, decision, lint, proof, LLM infra)

| Idea | Verdict | Attack / alternative |
|---|---|---|
| One `existing_answers()` for engine, worker, lint | **Agree: top-3** | Three disagreeing answers to "does this already exist?" is the governance bug behind several symptoms. It is also where the F1 id fix and the F2 full scan belong: one function, on ids, over the coverage index. |
| FALSE-CREATE metric + recall probes + "10 distinct texts" honesty | **Agree, do it before any number goes in the pitch** | My own F2 shows why: one recurring text inflated it 13x. Probes generated from the catalog avoid the circularity. |
| REUSE requires endorsement | **Disagree as a gate** | It trades a governance gap for more builds. 219/360 assets are unendorsed, so REUSE nearly disappears and "Build Less" becomes "build more". Labelled REUSE targets: AST-0247 promoted, 0292 and 0286 certified, 0328 none: 1 of 4 would flip. Alternative: **REUSE-with-conditions**. The verdict stays REUSE, and the failing gates become attached actions ("reuse AST-0191; certify it: owner X; refresh is OK"). Same gate checklist, opposite effect on the estate. |
| Lifecycle before choice | **Agree, and it is mandatory** (see section 0) | Without it, the full scan picks AST-0335 Legacy. |
| Net-zero estate (every build retires something) | Agree as story, **soften the rule** | A hard "net -1 or nothing" rule blocks legitimate CREATEs (Lynkuet launch: nothing to retire). Alternative: net change shown on every approval card and summed in the journal; a "net-positive" approval needs a typed reason. Same pressure, no deadlock. |
| Drop-and-show instead of STOPWORDS | Agree, with a guard | Dropping words is exactly how "ignore previous instructions" could slip through. The guard: dropped words always appear on the Intent receipt / RULE-ANSWER, and the negatives list runs on both paths before merge. |
| Merge interview + investigate into one call | **Disagree** | investigate takes `result.decision` as input (pipeline.py: `investigate(..., result.decision, estate, gaps)`), so it cannot run before decide. Merge **investigate + explain** instead: both run after the decision, on the same inputs, already in parallel. |
| Disagreement is a free hold-out | **Agree: best new idea in his audit** | Costs ~30 ms per request. The builder's pick labels it: an eval that grows from use. |
| Governance fuzzer on every push | Agree | S-M, and it is the quantitative proof Panu said is hard ("1,000 generated attacks, 0 wrong builds"). Pairs with my B4 replay. |
| DEMO_MODE for text calls, fail-fast timeout, temperature 0 | Agree, S each | Stage insurance; nothing to add. |
| 164 s test suite -> session fixture | Agree | Every push today costs ~95 s of the pre-push hook. |

## 4. gajus-chain.md (Gajus's other session)

| Idea | Verdict | Attack / alternative |
|---|---|---|
| Graph with connectors C1-C10 | **Agree: use it as the pipeline slide** | It is the logical sequence Panu asked for. Add per-connector "fixed / open" status as we go. |
| C9 floor request re-sent as free text | Agree | Pass the Intent, not text: same root as F1 (structure thrown away at a boundary). |
| Z1 earned permanence (ephemeral answers, minted on repeat demand) | **Agree: strongest "build less" story** | One conflict: Panu point 4 says one person approves *before anything enters the system*. An ephemeral view is not "in the system", so it holds. Say it explicitly in the pitch. |
| Z2 carrying cost + budget | Roadmap | The cost model inputs are guesses; a judge will ask "where does 7.5 h/month come from?". |
| Z5 KPI type checker | Agree, but **light version only** | Weights for the 3 ratio/stock KPIs. The numbers differ by under 1.3 points (his table), so it is correctness hygiene, not a demo moment. |
| Z6 governed answers API / MCP | Agree as the "why next year" line | 1 GET route is enough to show it. |
| Plan rank 3 "clean data dir" | Superseded | By the pending-change-set alternative above. |

## 5. New alternatives from combining the four audits (not in any audit)

1. **The gate checklist is the spine of the chain.** Margiris's verdict checklist + my B1 counterfactual + Martynas's
   gap-to-owner request + Donatas's RULE-ANSWER are the same object: an ordered list of named checks per candidate
   asset (covers KPIs, scope matches, period applied, endorsed, owner active, refresh healthy, not retiring, has source
   data). The first failing check on the best candidate decides three things at once:
   - the verdict (REUSE / EXTEND / CREATE / CLARIFY);
   - the attached action (certify, reassign, fix refresh, ask the KPI owner);
   - the receipt line.
   One data structure feeds decide, lint, explanation, the builder's to-do list and the pipeline slide.
2. **Deviation-ranked layout without targets.** Rank visuals by |deviation vs forecast or prior period| x better_is
   sign. "Most adverse first" works for all 12 bound KPIs today, no targets needed. The role envelope sets depth; the
   exception table appears only when it has rows (Donatas's empty-table point).
3. **Two-path agreement as a confidence signal.** Rules intent and LLM intent are computed anyway. Agree -> no
   interview question needed. Disagree -> the interview asks about exactly the field they disagree on. This makes the
   interview short by construction (Panu point 1) without the value-of-information machinery, and it reuses Margiris's
   disagreement log as labels.

## 6. My proposed order for DECISION.md
1. **Correctness of "does it already exist"** (one change):
   - F1 ids;
   - full coverage scan **with** lifecycle before choice;
   - one `existing_answers()` with containment;
   - RULE-001 on it.
   Owners: Gajus (intent), Margiris (engine, lint).
2. **Proof we can defend:** eval on the novice path, FALSE-CREATE, recall probes, "10 distinct texts" honesty, the
   12-measure Desktop check (Martynas, 5 min).
3. **Scope honesty:** the period field plus the RULE-ANSWER check at the Intent and at lint (Donatas + Martynas's
   calendar columns).
4. **No self-poisoning:** approvals as a pending change set; owner pick-list; `decision_hash` (Martynas S2, cheap
   version).
5. **Stage insurance:**
   - `make demo` loads the data pack (F3);
   - circuit breaker + AI-paused badge;
   - DEMO_MODE for text;
   - fail-fast timeout;
   - investigate + explain merged.
6. **One visible 0-to-1 for the judge:**
   - the gate checklist rendered as the receipt strip (section 5.1) on the deviation-ranked answer (5.2);
   - pitch lines: Z1 earned permanence and the disagreement hold-out;
   - everything else to the README roadmap.
