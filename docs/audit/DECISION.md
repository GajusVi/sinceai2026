# DECISION (draft for review): what we build from the audit

Drafted by Gajus's Claude, Sat 7 Nov 19:20.
- Sources: the four audits and four attacks in docs/audit/ (plus gajus-chain.md).
- Every item names its source and an owner.
- **Status: SIGNED by Gajus 19:45. C1-C6 decided, amendments A1-A9 accepted (below). The build resumes now with Tier 1.** Margiris's reply was still pending at signing; any objection from him becomes a follow-up, not a blocker. Each Claude replies on the board within 20 minutes: `ok` or an objection with evidence.
  Items marked **CONTESTED** are decided by Gajus.
- The build resumes from this file once Gajus signs it. Dibs rules still apply: claim a file you do not hold,
  Gajus OKs it, and you change OWNERS in the same commit.

## What the audit proved (agreed by all four)

1. **The engine is safe; it fails in the "build less" direction.**
   - False REUSE: 0 on every path (Martynas, 80 independent probes).
   - False CREATE on the novice (Intent) path: 15/40 with top-40 search, 4/40 with ids and a full scan (Martynas).
2. **Three root causes break the main path.**
   - Product names instead of ids at the Intent boundary (Gajus F1; confirmed by Donatas and Margiris).
   - The decision sees only the top-40 text hits (Gajus F2).
   - The REUSE check looks at the single best-scored candidate only (Martynas B1).
3. **Fixing the scan alone creates an attractor.** AST-0335 "All Pharma Growth Legacy" (owner inactive, RETIRE) wins
   unrelated requests and alone carries 54% of REUSE eligibility (Margiris N-A, Martynas B2). F2 ships only together
   with lifecycle-aware choice.
4. **Our proof measures the fallback, not the product.**
   - The eval runs the expert/rules path only.
   - The "150 requests" are 10 distinct texts.
   - There is no false-CREATE metric (Margiris, Martynas, Donatas, Gajus).
5. **The most visible wrong number is the period.** "LATAM this quarter" reads anywhere from EUR 249M to EUR 2,431M
   depending on the definition; today it shows 2,431M (all months) with every lint passing (Donatas, Martynas).
6. **Approvals poison later verdicts.** An approved EXTEND becomes an active, "refreshed today" asset (Donatas
   TL;DR 3).
7. **Stage risks.**
   - `make demo` loads the invented 19-asset catalog (Gajus F3).
   - The LLM fails silently (429 on every call during the audit) and changes answers (Margiris, Donatas).
   - 8 of 12 DAX measures have never been opened in Desktop (Martynas).

## The plan (ranked; tiers run in order, items inside a tier in parallel)

### Tier 1: correctness and stage safety. Nothing else merges until T1 is green.

| # | Change | Owner | Effort | Done when |
|---|---|---|---|---|
| T1.1 | `make demo` and `make ui` load the data pack (Makefile, run.ps1). | Gajus | 10 min | `make demo` shows REQ-0001's dashboard |
| T1.2 | **"Does it already exist", one PR** (details below the table). Owners: Gajus for the intent half, Margiris for engine and lint. | Gajus + Margiris | M, 3 h | T1.3 probes: Intent-path false CREATE <= 4/40, false REUSE 0, **and no chosen best asset carries RETIRE or a failed refresh** on the probes and the audit cases (Margiris, accepted 20:05) |
| T1.3 | **Proof on the real path** (details below the table). | Margiris + Martynas | S-M, 2 h | results.json shows both paths |
| T1.4 | Open Martynas's 12-measure check export in Desktop; compare with the expected values (**non-blocking**, A1). | Martynas (needs Windows + Desktop) | 5 min | 12/12 match or bugs filed |
| T1.5 | **Stage insurance** (details below the table). | Margiris (llm), Donatas (warm) | S, 1.5 h | 429 shows a badge, not a hang |
| T1.6 | **Approvals do not poison search** (details below the table). | Donatas (governance), Margiris (seed check) | S-M, 2 h | a rehearsal cannot change a stage verdict |

**T1.2 "Does it already exist":**
- Names map to ids once, at the Intent boundary (F1).
- The decision runs over a KPI -> assets coverage index on all assets (F2).
- Lifecycle comes before choice, and the best candidate is picked among REUSE-eligible ones first (Margiris + Martynas B1).
- Gates as decided in C2.
- One `existing_answers()` is used by engine, worker and lint. RULE-001 uses containment and offers a one-click
  "use AST-x instead".

**T1.3 Proof on the real path:**
- Martynas's probe generator (`data/build_probes.py`).
- The eval scores both paths.
- A FALSE-CREATE metric.
- `audit_cases.jsonl`: one row per audit repro (Margiris).
- Honest "10 distinct texts".
- Lint block rate.

**T1.5 Stage insurance:**
- Circuit breaker + "AI paused: rules mode" badge, with failure shown on the result.
- DEMO_MODE covers text calls.
- Timeouts per provider.
- Claude JSON at temperature 0.
- `make warm` covers the demo questions, including text calls.

**T1.6 Approvals do not poison search:**
- An EXTEND or CREATE from our app enters the catalog as `provisional`: it keeps the original `last_refreshed`, earns
  no trust until used or certified, and sunsets in 30 days unless reused.
- `make demo` copies a seeded data dir.
- A startup seed check replays the stage questions and refuses to start on any change.

### Tier 2: what the judge sees (starts when T1.2 and T1.3 are green)

| # | Change | Owner | Effort |
|---|---|---|---|
| T2.1 | **Period honesty** (details below the table; definition: C3). | Gajus (intent), Martynas (model), Margiris (lint), Donatas (cards) | M, 3 h |
| T2.2 | **An ordered answer** (details below the table). | Donatas (render) + Gajus (frontend) | M, 2-3 h |
| T2.3 | **Governance write side** (details below the table). | Donatas (governance) + Gajus (inbox, floor) | M, 2 h |
| T2.4 | **One decision, many views**: `decision_hash` next to `spec_hash`; the journal approves the decision hash and stores one view hash per role (cheap version of Martynas S2). | Martynas | S, 1 h |
| T2.5 | **The receipt strip** (details below the table). | Gajus | M, 2 h |

**T2.1 Period honesty:**
- `Intent.period` -> month filters.
- Period words in the parser; "quarter", "YTD" and "last month" are never dropped.
- `dim_month` calendar columns in semantic and in the TMDL.
- The period is printed on every card.
- RULE-ANSWER (every scope word applied or listed "not applied") at the Intent and in lint.

**T2.2 An ordered answer:**
- `RenderedDashboard.blocks` in step order, each block headed by its question.
- Only one role cut (delete the UI cut from 8fe651b).
- No silent drops.
- An empty threshold table becomes a positive line.
- Tone follows `better_is`.
- Layout order: business criticality, then signed deviation vs comparator, then template order (Martynas's two-key
  rule; no targets needed).

**T2.3 Governance write side:**
- Owner = pick-list of active owners.
- CREATE keeps the spec scope.
- `approve(user)` checks the permission.
- Send-back reaches the requester through one shared JSON inbox (gajus-chain N4).
- A floor request carries its Intent, not text (C9).
- Hash-chained journal; `propose` journals with verdict None.
- The approval card shows the net estate change (+1 / -0) and needs a reason when the net is positive (net-zero as a
  meter, not a gate).

**T2.5 The receipt strip:**
- One `Receipt {step, in, out, why, ms, llm_calls, failed}` per chain step.
- The gate checklist per candidate is its decide line (covers KPIs / scope / period / owner active / refresh healthy /
  not retiring / endorsed / has data). The first failing gate is the verdict's reason and the attached action
  (certify, reassign, fix refresh, ask the KPI owner).
- Shown beside the result for the BI team, and it is the pipeline slide (Panu point 8).

### Tier 3: if time allows (in this order)

| # | Change | Owner | Effort |
|---|---|---|---|
| T3.1 | Interview, short by construction (details below the table). | Gajus | M, 2-3 h |
| T3.2 | Builder health view (details below the table). | Martynas | S-M, 2-3 h |
| T3.3 | PBIP export (details below the table). | Martynas | M, 3 h |
| T3.4 | Merge investigate + explain into one call; fan out layout and takeaway after decide. | Margiris | S-M, 1.5 h |
| T3.5 | Gap -> governed data request to the KPI's named owner (Martynas A6). | Martynas + Donatas | M, 2 h |
| T3.6 | Session-scoped test fixture (164 s -> under a minute). | Margiris | S, 1 h |
| T3.7 | Delete legacy: backend/pipeline, main, ingest, audit; frontend/app.py; the sample catalog; golden_questions.json. Keep backend/llm.py + config.py, which the LLM path imports. | Gajus | S, 1 h |

**T3.1 Interview, short by construction:**
- Prefill from the login (plant, department).
- One confirmation turn showing the consequences.
- Rules vs LLM disagreement decides what to ask (gajus-attack 5.3).
- Value-of-information on the outcome triple (verdict, asset, headline numbers) only after T1.2 (Donatas).

**T3.2 Builder health view:**
- Root-cause grouping ("14 model fixes + 13 reassignments").
- Headline "16 certified assets on a failed refresh".
- Per-owner "my assets".
- Cache the parsed pack.
- Fix the quadratic duplicate scan.

**T3.3 PBIP export:**
- Title + subtitle (ground truth committed).
- Filters and the threshold table.
- `decision_hash` stamped in the model.
- A governance page inside the report.

### Roadmap (README, not built before the freeze)
- Self-checking approval with replay, plus PBIP drift detection (Donatas + Martynas, one loop).
- Earned permanence (Z1) beyond the provisional state of T1.6.
- Governed answers API / MCP (Z6).
- Demand ledger (B2).
- Requester-confirmed synonyms (B3, Margiris's version).
- Governance fuzzer.
- Disagreement hold-out with its own label source.
- `make conform` for any estate.
- Weighted aggregation as a governed field (C5).
- Self + company benchmark (not peers: 4 plants leak).
- Counts, not costs, for carrying load (Z2).

## Amendments accepted by Gajus (19:45)
- **A1 (Martynas):** T1.4, the Desktop check, is non-blocking: it changes no code and needs a human with Desktop.
- **A2 (Martynas):** `data/build_probes.py` stays independent of the engine (no imports from steward.decision or
  signals). Its labels carry two rule columns (today, C2), and the baseline run is committed **before** T1.2 merges.
- **A3 (Martynas, C3 gap):** paths that cannot ask (worker fast path, rules / LLM-off, API) read "this quarter" as
  **the last 3 complete months**, printed on the card ("Applied: Aug-Oct 2026"). The interview still asks when the
  period is ambiguous.
- **A4 (Martynas):** `provisional` is its own state with `expires_at`, outside the RETIRE funnel (which exempts assets
  younger than 3 months).
- **A5 (Martynas):** the layout ranks by **relative %** deviation x `better_is`, never absolute deviation. Criticality
  is the first key; the deviation decides ties.
- **A6 (Martynas), the T2.4 decision-hash definition:**
  - decision = verdict, change_type, base_asset_ids, kpi_ids, measures (name, kpi_id, expression, feasible), filters,
    owner_id, changes, source_model_id;
  - view = pages (order, steps, questions), with layout and provenance excluded.
- **A7 (Martynas):** H-05/H-06 are relabelled CREATE-with-labelled-gaps in the same commit as the C1 rule; the old
  label is kept as `label_v1`.
- **A8 (Donatas):** the seed check **warns** loudly; it never refuses to start (a refusal on stage is worse).
- **A9 (Donatas):** the shared JSON inbox (T2.3) moves to Gajus. Pitch, pipeline slide and demo video get
  **02:00-06:00** on the frozen build.
- **Dependency:** T1.5 "warm covers text calls" needs an LLM key with quota (Gemini returned 429 all evening). Whoever
  has quota runs it, or warm runs on another provider.

## CONTESTED: decided by Gajus (19:35)
- **C1 A:** EXTEND needs at least half of the requested KPIs (REQ-0001 -> CREATE; update golden + hold-out labels in the same commit).
- **C2 mixed:** RETIRE or failed refresh blocks REUSE and demotes an EXTEND base; inactive owner = REUSE + REASSIGN_OWNER; endorsement = attached "certify" action.
- **C3 A:** ask about the period only when it is ambiguous (options show their numbers); "Applied: <period>" on every card.
- **C4 B:** provisional + 30-day sunset, no trust until used or certified.
- **C5 B:** no number change tonight; "simple mean (assumption)" on the receipt.
- **C6:** the receipt strip with the gate checklist is the spine; the net-zero meter is on the approval card; the governed API is the "next year" line.

### Options as drafted

| # | Question | Options | Recommendation |
|---|---|---|---|
| C1 | **EXTEND needs at least half of the requested KPIs** (filters stop counting as covered items for EXTEND). See notes below. | A: take the rule. B: keep today's item count. | **A.** "An honest CREATE, with proof that nothing covers it" beats "extend a retiring legacy report". |
| C2 | **Which checks block a REUSE?** See notes below. | A (Margiris): owner inactive, RETIRE or failed refresh blocks REUSE and demotes an EXTEND base. B (Martynas): no blocks, only a ranking key, and the failures shown as flags. A3 (both rejected it): endorsement as a hard gate. | **A for RETIRE and failed refresh** (a reused report must work and must not be on its way out). **Inactive owner = REUSE with REASSIGN_OWNER attached.** Endorsement = an attached "certify" action, never a gate. |
| C3 | **What "this quarter" means** (on 7 Nov the readings span EUR 249M-2,431M). | A (Donatas): ask only when it is ambiguous, options show their numbers; unambiguous periods are applied. B (Martynas): one fixed rule ("the last 3 complete months"), printed on the card. | **A.** One tap, the consequence visible, and "Applied: <period>" on every card either way. |
| C4 | **Earned permanence** | A: ephemeral views outside the catalog until demand repeats (gajus-chain Z1). B: everything enters the catalog as `provisional` with a 30-day sunset and no trust until used (Donatas, Margiris, Martynas). | **B** (in T1.6). An ephemeral view breaks Panu point 4 ("approved before it enters") and cannot be found by the next request. |
| C5 | **Weighted means for OTIF, forecast accuracy, inventory** (gaps up to 10%) | A: change the numbers tonight (units-weighted). B: no number change; the receipt says "aggregation not governed: simple mean (assumption)"; weights become a governed field later. | **B.** The weight is a KPI definition, its owner's call (Donatas); changing it re-opens Desktop verification and the pitch numbers. |
| C6 | **The one 0-to-1 we lead the pitch with** | A: the receipt strip with the gate checklist (Gajus/Margiris; it is Panu's point 8). B: governed answers API (Martynas). C: net-zero estate meter (Margiris/Donatas). D: a governance page inside the PBIP (Martynas). | **A as the product's spine, with C on the approval card.** B is the "next year" closing line. D goes in if T3.3 lands. |

**C1 notes:**
- REQ-0001 becomes CREATE (golden and pitch example change).
- H-01 becomes correct: hold-out 22 -> 23/25.
- H-05/H-06 become CREATE. That conflicts with the earlier answer "EXTEND with gaps"; take the new rule.

**C2 notes:**
- Endorsement is not a gate (3/3 demo REUSE would vanish).
- The question is RETIRE, failed refresh and inactive owner.

## Timeline proposal
- **19:45:** replies to this draft.
- **20:00:** Gajus signs C1-C6 and the build resumes with Tier 1.
- **22:30:** Tier 1 green; Tier 2 starts.
- **02:00:** freeze; Tier 3 only if Tier 2 is done.
- **02:00-06:00:** pitch, pipeline slide and demo video on the frozen build (Donatas, A9).
- **Sun 08:00:** submission.
