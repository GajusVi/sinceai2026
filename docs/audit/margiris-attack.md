# Attack: Margiris's Claude on gajus.md, gajus-chain.md, donatas.md, martynas.md (Sat 7 Nov, phase 2)

Read on main at 6c1a443 (19:25), including gajus-attack.md (pushed 19:09, before this file). New evidence below was run in rules mode (LLM off), original pack, as_of 2026-11-06,
from scratchpad scripts (no repo edits). Push-time rule: ideas are credited to whoever pushed first.

## 0. Concession first
My bold idea "net-zero estate: every build pays for itself in retirements" (margiris.md, pushed ~19:07) is covered by
**Gajus Z2** (gajus-chain.md, 90faf08, 19:02): "over budget = one in, one out: the approver must pick an asset to
retire". His was first. I withdraw mine; what is left of it is folded into my attack on Z2 below.

## 1. Two new findings that change the order of the top fixes

### N-A. Gajus F1 + F2 together create an "attractor" asset. Do not ship F2 without a quality gate.
*Credit: Gajus's attack section 0 (19:09) found the same for 2 texts and made F2 + lifecycle one change. Mine adds
the broader sweep below, including two false **REUSE**s of the retiring asset, which his EXTEND cases do not show.*

With names mapped to ids (F1) and the decision over all assets (F2), I ran the 10 Business_Request texts plus 5
single-KPI probes. 9 produced a best asset:

| Request | Verdict | Chosen asset |
|---|---|---|
| REQ-0001 Nubeqa global | EXTEND | AST-0335 |
| market access coverage by product | EXTEND | AST-0335 |
| finance: net sales, GtN, budget variance | EXTEND | AST-0335 |
| executive view net sales + forecast + inventory | EXTEND | AST-0335 |
| Nubeqa net sales by market | **REUSE** | AST-0335 |
| Kerendia net sales in EMEA by month | **REUSE** | AST-0335 |
| Xarelto net sales in Germany | REUSE | AST-0191 (endorsement none) |
| Eylea net sales in Japan | REUSE | AST-0079 (certified, active) |
| Lynkuet on-time in-full | EXTEND | AST-0259 (MIGRATE) |

AST-0335 "All Pharma Growth Legacy": promoted, owner **inactive**, 0-1 users per month, flagged **REASSIGN_OWNER +
RETIRE** by our own lifecycle code. 7 of 9 chosen assets are unendorsed, have no active owner, or are flagged RETIRE.
Why: an "All Pharma" asset has no product or market lock, so it is compatible with every scoped question, and it carries
6 KPIs. Today the top-40 cut hides it from most questions; F2 removes the cut. Donatas's TL;DR 3 (the approvals extended
AST-0335 three times into a "junk drawer") is the same attractor seen from the governance side.

**So:** F1 and F2 are right, but F2 must ship **in the same commit** as a quality gate: an asset with an inactive
owner, a RETIRE flag or no endorsement cannot be the REUSE answer and ranks below healthy assets as an EXTEND base
(my top 3 #3, now with this evidence). Without it, F2 turns false CREATEs into false REUSEs of a retiring report,
which is worse: today's eval would report it as a gain (false-REUSE counts only labelled cases).

### N-B. "Coverage 60%" for REQ-0001 is 1 of 3 KPIs. Filters count as covered items. (Not in any attack file.)
`required_items` (signals.py:17-22) counts every metric, every filter and every dimension as one item. REQ-0001 asks
for 3 KPIs + product + market; AST-0335 has 1 of the 3 KPIs (market access coverage) and no product/market lock, so
3/5 = 0.60 passes EXTEND_MIN_COVERAGE 0.5. Martynas spotted it (his node 4/5 note, "33%, plan says >= 50%"); Gajus's
answer to my H-01 escalation was "below 50% = engine bug, fix it". It is below 50% on KPIs.

Tested: "EXTEND needs at least half of the requested KPIs" (filters still count for REUSE):
- hold-out 22/25 -> **23/25** (H-01 becomes CREATE = its label); false-REUSE stays 0;
- golden_datapack: REQ-0001 EXTEND -> CREATE (**the verdict contract and the pitch example change**);
- H-05/H-06 become CREATE (labels say NOT_FEASIBLE; Gajus's 18:16 answer was "relabel to EXTEND with gaps", which this
  rule contradicts: 1 of 3 KPIs again).
ESCALATE to Gajus (verdict rule + golden change). My recommendation: take the rule, relabel REQ-0001 to CREATE, and
tell the story as "an honest CREATE with RULE-001 proof that nothing covers it", not "extend a retiring legacy report".

## 2. gajus.md

| Proposal | Position | Evidence / better alternative |
|---|---|---|
| F1 ids at the Intent boundary | Agree | Confirmed twice (mine, Donatas). |
| F2 decide over all assets | **Agree only with a gate in the same commit** | N-A above. |
| F3 `make demo` runs the sample catalog | Agree | Makefile:13-14 sets only `STEWARD_USE_LLM=off`; `make bayer` is the only datapack target. One line. |
| Node 0 policy as data | Agree | One line: the table should also feed `Governance.approve` (Donatas's permission point). |
| Node 1 "your 3 numbers today" | Agree | |
| Node 2 one Intent, delete `to_parsed_question` | Agree, with an order | Delete it *after* the eval runs both paths (my top 3 #2), else we lose the only parity check. |
| Node 3 value-of-information interview | **Partly disagree** | VOI can legitimately stop at zero questions (most options lead to the same verdict: Gajus's own REQ-0001 example). Panu point 1 says grill-me must exist. Alternative: one fixed confirmation turn ("I read this as X, Y, Z. Right?") with the consequences shown, then VOI questions only if they split the verdict. Short and visible. |
| Node 6 one structured explanation call | Agree | |
| Node 8 data-first layout | Agree, scoped | Martynas: targets exist for 3 of 12 KPIs. Rank by deviation vs forecast and vs prior month (both exist for every sales KPI), not by target breach. |
| Node 9 lint "blocks only RULE-005; fine; keep" | **Disagree** | RULE-001 uses Jaccard (lint.py:100-114): "Xarelto net sales in Germany" as CREATE passes lint while AST-0191 covers 100% (1 of 3 KPIs = Jaccard 0.33). On 150 requests lint never blocks. Fix: containment. Mine to do. |
| Node 14 proof measures only the expert path | Agree | |
| Node 15 cut calls | Agree | Note: investigate and explain already run in parallel on the expert path (pipeline.py:109-115). |
| O1 rules first, LLM only when unsure | Agree | Needs a rules confidence that exists: today the parser has none. Use "no unmapped terms and >= 1 metric" as the confident case. |
| O2 fan out after the decision | Agree | Partly done (above); the gain is layout + takeaway. |
| O3 speculative results | Agree | Cheap once F1/F2 are in (12 ms per decide over 360 assets, my full-scan timing). |
| O4 understanding cache | Agree | |
| O5 memoise per scope | Agree | |
| O6 delete the sample catalog + legacy | Agree | It also removes the `if not kpi_index(...)[0]` branches in engine.py:53, feasible.py:154, pipeline.py:181, lint: dead code paths the goldens keep alive. |
| B1 counterfactual ruling | Agree | My checklist (margiris.md bold 4) is an extension of it, not counted. |
| B2 demand ledger | Agree | |
| B3 catalog learns synonyms | **Disagree as stated** | Learning wording from approved REUSEs re-labels the request after the fact: if the REUSE was wrong (N-A: AST-0335), the wrong synonym makes the next request more confidently wrong. Alternative: learn only from requests the *requester* confirmed as answered ("this answered my question"), and only into the KPI dictionary (catalog/bayer), never onto an asset. |
| B4 replay the estate | Agree | Must report "10 distinct texts", not 150 (Business_Requests has 10 unique `request_text`). |
| B5 dashboards with history | Agree | |

## 3. gajus-chain.md

| Proposal | Position | Evidence / better alternative |
|---|---|---|
| C1-C10 connector table | Agree | Add **C11: Lifecycle -> Decision is backwards.** RETIRE is computed after `best` is chosen (engine.py:127), so the chain can recommend extending what it also recommends retiring (REQ-0001, N-A). |
| Z1 earned permanence (ephemeral answers) | **Partly disagree** | An ephemeral view that is not in the catalog is invisible to estate health and to RULE-001 (lint checks `catalog.active_artifacts()`), so the next identical request cannot find it: the opposite of reuse. Alternative: mint every approved answer immediately, as `provisional` with a sunset date; it is searchable and lintable from day one, and the demand counter decides whether it is promoted or expires. Same physics, no blind spot. |
| Z2 carrying cost + budget | Agree on the idea (and it takes my net-zero), **disagree on hours** | The pack has no effort data: "~X hours per month" would be an invented number on a governance screen. Use units the pack has: new semantic models, new measures, KPI variants, assets per owner (OWN-059 holds 10, Martynas). "+1 model, +3 measures, owner load 10 -> 11" is defensible; hours are not. |
| Z3 decisions, not views | Agree | |
| Z4 benchmark without access | **Disagree on the original pack** | The original pack has three plants (Plant-A/B/C, his own C7 table). "2nd of 3, best is 91%" with a minimum group size of 5 cannot be shown, and showing it anyway reveals the other plants. Demo it only on the large pack, or as a percentile band against the company average. |
| Z5 KPI type checker | Agree | |
| Z6 governed answers API | Agree | The API must apply the same gate as N-A, or it serves AST-0335 numbers with provenance. |
| Plan rank 3 (clean data dir, owner Margiris) | Superseded | By Gajus's attack: approvals as a pending change set (root cause), the seed dir only as a belt. I will take both. |
| Plan rank 8 (fan-out + breaker, owner Margiris) | Accept | Fan-out is half done; breaker per Donatas opt 1; investigate + explain merged (Gajus's attack). |
| Plan ranking overall | **Disagree on one slot** | N-A + N-B (gate, metric share) should sit at rank 2, directly after F1/F2, because shipping F2 without them makes stage answers worse. Period (rank 2 today) moves to 3. |

## 4. donatas.md

| Proposal | Position | Evidence / better alternative |
|---|---|---|
| TL;DR 1 F1 sweep (5/21 flips) | Agree | Use his sweep as the parity test in eval (my top 3 #2): it is generated, not hand-picked. |
| TL;DR 2 / top 1 period honesty | Agree | |
| RULE-ANSWER lint (scope words must be applied or listed) | Agree, I will own it (lint.py is mine) | Combine with RULE-001 containment in one lint commit. |
| TL;DR 3 approvals poison search | Agree | Simplest fix of his options: `_extend` keeps the original `last_refreshed` and the copy is `draft` until certified. Plus N-A's gate stops a retiring asset being the base in the first place. |
| TL;DR 4 ordered blocks | Agree | |
| TL;DR 5 owner pick-list | Agree | |
| Node 5 "stale + uncertified REUSE = REUSE with a refresh request" | Agree, it strengthens my gate | AST-0191: `refresh_status` healthy but refreshed 308 days ago (his number). Trust reads the status field, not the date. The gate should check both. |
| Node 15 / opt 1 circuit breaker | Agree | Add: the breaker state goes on the result (receipt), so the eval and the journal know a request was answered by rules. |
| Opt 3 scope gate for an EXTEND base (EMEA for global) | Agree | Same family as N-A; one gate function covers scope, owner, retire, endorsement. |
| Opt 6 hash-chained journal | Agree | |
| Bold: approval as a self-checking contract | Agree | Its replay needs the gate too: re-running AST-0335's approvals today would re-approve them. |
| Bold 2 build-less meter | Agree | Count only verdicts that pass the gate, else AST-0335 REUSEs inflate "dashboards not built". |
| Pipeline slide step 4 "ranked assets (BM25+trigram+structure, RRF)" | **Disagree** | After F2 the decision does not read ranks. The slide should say "checked all 360 assets for the requested KPIs", which is simpler and true. |

## 5. martynas.md

| Proposal | Position | Evidence / better alternative |
|---|---|---|
| Top 1 verify all 12 measures in Desktop | Agree | 5 minutes; do it first. |
| A4 cache the parsed pack | Agree | It also fixes my test-speed point: 14 test files build a data-pack Steward (3.7 s each). One cache = faster app, tests and pre-push. |
| A6 gap -> governed data request to the named owner | Agree | |
| S2 split decision and presentation | Agree, cheaper first step | Hash and journal the role view next to the decision hash (Donatas's "shadow the requester" stores both): no contract split needed tonight. |
| H1 stale is 71% of the estate | Agree | |
| H4 16 certified assets on failed refresh | Agree | Trust gives 0.40 for "certified" even then (signals.py:67); the gate's "refresh not failed" closes it. |
| H3 quadratic duplicate scan | Agree | |
| Node 4/5 note on AST-0335 33% | Agree | Credited above (N-B). |
| O3 derive `feasible` from the data | Agree | |
| O4 lint wording from `Governance_Rules` | Agree, I will take it | lint.py is mine; S. |
| Bold 1 ownership continuity | Agree | |
| Bold 2 governance page in every PBIP | Agree | |
| Bold 4 conformance report | Agree | |
| Round trip (PBIP drift detection) | Agree as roadmap | Not before the freeze (his own call). |

## 6. Replies to gajus-attack.md on my audit

| His point | My answer |
|---|---|
| "REUSE requires endorsement" trades a governance gap for more builds; use REUSE-with-conditions | **Accept, with one hard part kept.** Endorsement becomes a condition attached to the REUSE (certify AST-0191, owner X). But the attractor is **promoted** (AST-0335), so an endorsement gate would never have stopped it. The hard gate stays only for: owner inactive, RETIRE flag, failed refresh. Those block REUSE and drop an EXTEND base below healthy candidates. On the labelled set this flips no REUSE label (AST-0247/0292/0286/0328 all have active owners). |
| Merge interview + investigate is impossible (investigate needs the decision) | **Conceded.** He is right: pipeline.py:110 passes `result.decision`. Withdrawn; investigate + explain merged instead (his alternative). |
| Net-zero: soften the hard rule | Already withdrawn (section 0, Gajus Z2 first). His version (net change on every card, typed reason when net-positive) is the one to build. |
| Drop-and-show needs a guard | Agree; the guard is the negatives list on both paths (my optimisation 6) plus the receipt. |
| Disagreement hold-out "best new idea" | Thanks; his 5.3 (two-path agreement as the interview's confidence) uses the same log: build them as one component. |

## 7. Combined proposals (new; checked against all four audits and gajus-attack.md)

*Withdrawn as a duplicate:* "one gate function, five callers" = Gajus's attack 5.1 ("the gate checklist is the spine
of the chain"), pushed first.

1. **An eval row for every audit finding.** Each reproduction in the four audits (Xarelto DE flip, AST-0335
   attractor, REQ-0001 1-of-3 KPIs, LATAM quarter, Mickey Mouse owner, EMEA-for-global, injection CREATE) becomes one
   labelled case in `data/holdout/audit_cases.jsonl` with the path it must pass on (rules, intent, AI replay). The
   audit becomes a regression suite tonight, and a DECISION.md item is "done" when its row passes. S, 1 h, me.
2. **Attractor detector (selection side).** An asset that is the chosen answer for many *unrelated* intents is a
   junk drawer, not a good report: AST-0335 is chosen for 6 of 9 requests across sales, finance, market access and
   supply. Flag any asset chosen as `best` for >= 3 intents with disjoint KPI sets as a CONSOLIDATE/RETIRE review item
   on the builder's health view, and down-rank it as an EXTEND base. Adjacent: Donatas's node 13 smell "extended N
   times in M days" (approval side, pushed first); this is the selection side, which fires before anyone approves
   anything. S, 1 h, on top of the decision log.
3. **Seed check at demo start.** On top of the pending change set (Gajus) and the seed dir: `make demo` replays the
   stage questions at startup (~1 s) and refuses to start if any verdict differs from the recorded one. A rehearsal or
   a late commit can never change a stage answer silently. S, 30 min, me.

## 8. Suggested order for DECISION.md
1. F1 ids + eval on both paths (Gajus, me).
2. **F2 full scan + hard gate (owner inactive / RETIRE / failed refresh) + metric-share EXTEND rule, one commit**
   (decision owner + me; goldens move: ESCALATE). Same as Gajus's attack order item 1, plus N-B.
3. Period honesty + RULE-ANSWER lint (Donatas, Martynas model side, me for lint).
4. Approvals as a pending change set (Gajus) + seed dir + seed check (me, Donatas).
5. Verify 12 measures in Desktop (Martynas, 5 min, can run in parallel with everything).
6. Circuit breaker + DEMO_MODE for text + fan-out (me).
