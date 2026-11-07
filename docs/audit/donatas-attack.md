# Attack: Donatas (phase 2) — Sat 7 Nov 19:25

Read on main at 13708f1:
- gajus.md, including O1-O6 / B1-B5 (f85f638) and gajus-chain.md (90faf08);
- margiris.md (8fa8783);
- martynas.md (0e20c10).

Evidence was run on the original pack in rules mode with a clean data dir, unless a line says otherwise. Scripts are in
my scratchpad. Rule 18:50 applies: alternatives marked **new** are not in any audit on main. Ideas from others are
cited by author and id.

## Duplicates with gajus-attack.md (6c1a443, pushed 19:09, before me): his, not counted as mine
- "REUSE-with-conditions" instead of Margiris's endorsement gate = **his**. I add only evidence E1: on the demo
  pack the gate removes 3 of 3 REUSE (he counted 1 of 4 labelled targets).
- "Merge investigate + explain, not interview + investigate" = **his**. E2 is the same evidence.
- "F2 full scan only with lifecycle before choice" = **his** self-correction.
- "Approvals as a pending change set" (my C3 fix) = **his**. The only new part I keep is the **30-day sunset unless
  reused** for Steward-born assets (alternative 2 below).
- "`decision_hash` next to `spec_hash`" (cheap version of Martynas S2) = **his**.

## My answers to Gajus's attack on my audit
- **Seed dir hides the bug:** accepted. The pending change set is the fix; the seed dir stays as a belt for the
  stage.
- **RULE-ANSWER at the Intent as well as at lint:** accepted. One function, two call sites. The Intent call site
  asks only about **ambiguous** periods ("this quarter" on 6 Nov = Q4-to-date, Oct only, or the last complete
  quarter Jul-Sep). An unambiguous period ("October", "YTD") is applied without asking.
- **Replay is too big tonight:** accepted. README roadmap, base for Martynas's drift check and his B5.
- **Shadow the requester is superseded by the decision/view split:** accepted. It is the approval-screen UI of
  Martynas S2.

## 0. Four facts that change other people's proposals
| # | Fact | Command / source | Hits |
|---|---|---|---|
| E1 | In a 28-question product sweep ("<product> net sales [in Germany / by month]", "<product> OTIF") there are only **3 REUSE answers, all on AST-0191, endorsement `none`, certified False**. | `s.ask()` over `dim_product` x 4 templates | Margiris top 3 #3 |
| E2 | `investigate()` takes the `Decision` as an argument (`steward/investigate.py:69-76`). It runs **after** decide. The interview runs **before**. | code | Margiris opt 15.3 |
| E3 | The original pack has **4 supply sources** (Plant-A, B, C, External-CMO; `fact_supply.supply_source`). | `semantic.load_frames()` | Gajus Z4 (minimum group 5) |
| E4 | Business_Requests: **150 rows, 10 distinct `request_text`**. | `read_excel`, `nunique()` | Gajus B4, (Margiris already said it) |

---

## Gajus (gajus.md + gajus-chain.md)

### Disagree
1. **Node 3, value-of-information grill-me: "ask only what changes the verdict".**
   - **Why it fails:** the period does not change the verdict, but it changes the number. "LATAM this quarter" gives
     the same EXTEND for Q4 or for Jan-Oct, yet the card says EUR 692 M vs EUR 2,431 M (my TL;DR 2). A VOI interview
     scored on verdict alone would never ask "which period?" and would ship a 3.5x wrong number confidently. The same
     goes for site, market and product filters on a REUSE: same asset, different numbers.
   - **Better, new:** score each candidate answer by the **outcome triple (verdict, best asset, headline numbers)**,
     not by verdict alone. Two answers that give the same verdict but headline numbers more than 5 % apart still count
     as "worth asking". `semantic.compute` on a card is 0.01 s warm (my trace), so this stays well under 1 s.
     Plus a hard rule: a period word the user typed is never asked, it is applied.
2. **Z1, earned permanence (ephemeral until demand repeats).** (Gajus's attack says Z1 holds because "an ephemeral
   view is not in the system". **We disagree; Gajus decides.** My point: the number is *shown* to people as governed,
   which is what "entering the system" means to a Bayer reader.)
   - **Why it fails:**
     - Panu point 4: "one person approves **before anything new enters the system**". An ephemeral view that is
       shown to people but is not an asset is a governed number with no owner and no catalog entry. That is a
       shadow dashboard, which is the thing the brief wants gone.
     - The next requester cannot REUSE something that is not in the catalog, so the "demand repeats" counter has
       nothing to find unless search also indexes ephemerals. Once it does, they are assets in all but name.
   - **Keep the good half, new combination:** keep the **sunset date at birth** (Z1) and use it to fix my C3. Assets
     born from our approvals (`catalog_changes.json`) enter the catalog as `draft`. They get no trust from
     "refreshed today" until they are actually used, and they sunset in 30 days unless reused. That solves both
     "rehearsals poison search" (C3) and "sprawl at birth" without an un-catalogued object.
3. **Z2, carrying cost and a team budget.**
   - **Why it fails:** "~X maintenance hours per month, budget 120, used 113" needs numbers the pack does not have
     (there are no hours or budgets in the 24 sheets). On stage it is an invented metric next to governed ones, and a
     judge asking "where does 113 come from?" sinks the governance story. Panu point 7: quantitative is hard here,
     argue qualitatively.
   - **Better:** count what the pack does have and price nothing. "+1 asset, +2 KPI variants, +1 semantic model
     refresh, owner OWN-059 already holds 10". Real counts, no currency.
4. **Z4, benchmark without access.**
   - **Why it fails:** E3. With 4 supply sources a rank and a best value from a group of 4 de-anonymises the others
     (3 plants + CMO: "best is 91 %" is one specific plant). It is below Gajus's own minimum of 5. It only works on the
     large pack, and the large pack is not the demo pack (goldens and pitch numbers are on the original).
   - **Better, new:** **benchmark against yourself and the company**, which leaks nothing. "Plant-B OTIF 78.3 %:
     lowest of its last 10 months; company 82.6 %." Both numbers are already computable (company = no site filter).
5. **B4, replay the estate in front of the judge ("all 150 Bayer requests").**
   - **Why it fails:** E4. 150 = 10 texts x 15. A judge who opens the sheet sees the same sentence 15 times, and our
     "quantitative proof" becomes a credibility problem.
   - **Better (combination):** replay the **10 distinct texts plus Margiris's generated fuzzer cases** (her bold 3),
     and say "10 real + N generated, every generated case has a known correct outcome". Honest and larger.
6. **gajus-chain rank 3 owner.** "Clean data dir per demo + approvals do not poison search" is assigned to Margiris.
   The write side is `steward/governance.py` and the demo targets, which are mine. Search ranking is only half of
   it. **Suggest: Donatas** (governance + seed dir), Margiris for the ranking tie-break (my alternative to Z1 above).

### Agree (one line each)
- F1 names vs ids: yes, #1. I confirmed it blind and found the outage path too.
- F2 top-40 cut: yes, but only together with fix 2 above (see Margiris disagreement 3).
- F3 `make demo` loads the sample catalog: yes, confirmed (`Makefile:13-14` sets only `STEWARD_USE_LLM=off`). It is
  the cheapest fix in the whole audit and must go first.
- Policy as data (node 0): yes.
- "Your 3 numbers today" (node 1): yes; it is my floor push in reverse (pull on login).
- Ruling as a document (node 6): yes.
- Data-first layout (node 8): yes, ranked by deviation vs forecast / prior month, which exists for all 12 KPIs.
  Martynas's caveat holds: targets exist for 3 of 12.
- O1 rules first: yes.
- O2 fan out: yes.
- O4 understanding cache: yes, merged with my layout memo (one cache module).
- O5 memoise: yes.
- O6 delete legacy: yes, and it makes F3 impossible.
- B1 counterfactual ruling: yes.
- B2 demand ledger: yes.
- B3 governed synonyms: yes.
- B5 history diff: yes; my replay produces exactly the diff it would show.
- C9 (floor request re-sent as text): yes.
- C10 (dept map `missing` unused): yes.
- Z5 KPI type checker: yes, see Martynas below for the owner of the truth.
- Z6 governed answers API: yes as the roadmap line; do not build it before the freeze.

---

## Margiris (margiris.md)

### Disagree
1. **Top 3 #3: "REUSE needs an endorsement".**
   - **Why it fails:** E1. On the demo pack every REUSE I can produce lands on the unendorsed AST-0191, and 219 of 360
     assets are unendorsed (her number). The gate turns **3 of 3 REUSE into EXTEND or CREATE**, so the demo shows
     **zero REUSE**. For a challenge called "Build Less", that is a tool which never says "it already exists". It also
     moves the decision from "does it answer?" to "is it blessed?", which tells the requester to build a copy of a
     report that answers them.
   - **Better, new: "REUSE, uncertified" as a ticket, not a different verdict.** The verdict stays REUSE. The card
     says "answers your question; not certified: OWN-xx asked to certify", and the journal logs a certification
     request against the asset. This is Gajus's B1 counterfactual applied to trust instead of coverage. The asked-for
     number stays reusable, and the estate gets better from demand.
2. **Opt 15.3: "merge interview + investigate into one call".**
   - **Why it fails:** E2. Investigate reads the decision; the interview runs before there is a decision. Merging
     them means the LLM drafts the investigation before the rules engine has decided. That breaks our core claim
     (CLAUDE.md: "The verdict is rule-based code; the LLM only parses the question and rewrites the explanation").
   - **Better:** Gajus's O2 (fan out after decide) gets the latency win without breaking the order. If one more call
     must go, merge **investigate + explain** (both after decide, same dossier). That is Gajus node 6, his idea.
3. **Node 4, "decide over all 360 assets" (= Gajus F2, her evidence), shipped alone.**
   - **Why it fails:** her own trace shows the full-scan winners are AST-0335 "All Pharma Growth Legacy" (owner
     inactive, RETIRE). On my dirty data dir, AST-0335-v4 (our own approved copy, "refreshed today", 0 views) wins.
     A wider candidate set without a lifecycle-aware ranking promotes exactly the assets health wants to retire, and
     the copies our rehearsals made.
   - **Better (combination):** ship F2 **with** her "lifecycle before choice" ranking **and** my "Steward-born drafts
     earn no trust until used". F2 alone is a regression on this estate.
4. **Opt 15.2: "timeout 10 s instead of 45 s x 3".** It is right for Gemini, but Gajus quotes Margiris at ~25 s per
   Aitta call, so a 10 s timeout fails every Aitta call. Make the timeout per provider in `backend/config.py`, not one
   number.

### Agree (one line each)
- One `existing_answers()` for engine, worker and lint (top 1): yes, the best structural fix in any audit.
- FALSE-CREATE metric + recall probes + honest "10 distinct texts" (top 2): yes.
- RULE-001 containment instead of Jaccard: yes. Lint must also offer the switch: "AST-0191 answers this: use it",
  one click to REUSE, otherwise approve is just a dead end.
- "Drop and show" (opt 1): yes, **only with** a RULE-ANSWER lint (my top 1). A dropped word must appear on the card,
  not just in the trail, or "Xarelto net sales excluding hospitals" becomes a confident REUSE of the unfiltered
  number.
- Session-scoped test fixture (opt 2): yes.
- DEMO_MODE for text calls (opt 3): yes, and I own `make warm`, so I will extend the warm script to cover text calls.
- Claude temperature 0 (opt 4): yes.
- Delete trigram/RRF from the decision path (opt 5): yes, after F2.
- Negatives in AI mode (opt 6): yes, after warm.
- Lint block rate (opt 7): yes.
- Dedupe engine code (opt 8): yes.
- Net-zero estate (bold 1): yes as the pitch line. Approval shows "+1 / -2 / net -1".
- Disagreement as a free hold-out (bold 2): yes.
- Governance fuzzer (bold 3): yes, and it is the honest replacement for B4's 150.
- The "receipt must show failure and rejection" (node 15): yes. Today, with 24 of 24 calls failed, the UI says
  nothing (I saw the same).

---

## Martynas (martynas.md)

### Disagree
1. **Weighted averages / Z5 type checker (Gajus C7 + Z5, Martynas A3): who picks the weight?**
   - **Why it fails as written:** both audits choose the aggregation themselves (units-weighted). The governed
     definition belongs to the KPI owner. If our app silently switches Plant-B OTIF from 78.3 % to 77.0 %, our number
     disagrees with every existing Bayer report that uses the simple mean. That is a variant KPI born in our tool,
     which RULE-002 exists to stop.
   - **Better, new:** the aggregation is a **field of the governed definition** (`measures.json`
     `aggregation: mean|weighted_by:<col>|last`), filled from the pack's KPI_Catalog formula where it says so, and
     otherwise marked "aggregation not governed: simple mean (assumption)" on the receipt. The type checker
     (Gajus Z5) then enforces the governed choice rather than inventing it.
2. **Top 1, "verify all 12 measures in Desktop", as the #1 change.** It is real stage risk, but it is a 5-minute
   manual check (his own estimate), not a change. Do it tonight as a task, not a slot in DECISION.md's ranking. It
   should not displace F1, F3 or the period fix.

### Agree (one line each)
- A1 period dropped: yes (my finding, his model-side calendar is the right second half).
- O1 calendar in `dim_month` + TMDL: yes, this is how `Intent.period` should land.
- A4 cache the parsed pack: yes.
- H3 quadratic duplicate scan: yes.
- S2 "one request, three specs, one approved": yes. It is the same defect as my "two role cuts". Combine: approve
  the **decision hash**, show each role's **view hash** (his split). My "shadow the requester" is the approval
  screen for it.
- S1 dead fields, S3 typed provenance: yes.
- P5 PBIP edited in Desktop / round-trip drift: yes, roadmap.
- H4 "16 certified assets on a failed refresh" as the estate headline: yes, strongest single number for the builder
  persona.
- O2 group problems by root cause (14 model fixes + 13 reassignments): yes. It is the per-builder view Panu asked for.
- O3 derive `feasible` from the data: yes.
- O4 rule text from the Governance_Rules sheet: yes.
- O5 `check.json` in the zip: yes.
- Bold 1 ownership continuity with a successor chain: yes. It sits on top of my owner pick-list.
- Bold 2 governance page inside the PBIP: yes, cheapest way for the file to prove itself without our app.
- Bold 3 "show your work" on every number: yes (adjacent to my withdrawn receipt-per-number; his, pushed first).
- Bold 4 `make conform`: yes.
- Node 0 "build() does not scope to plant": yes, I saw the same.

---

## New alternatives from this attack (not in any audit on main)
1. **VOI on the outcome triple** (verdict, asset, headline numbers) instead of the verdict alone; typed period words
   are applied, never asked. (Gajus node 3)
2. **Steward-born assets are drafts with a sunset**: no trust from "refreshed today", sunset in 30 days unless reused.
   Takes Z1's sunset and drops its un-catalogued view. (Gajus Z1, my C3)
3. **Counts, not costs, on the approve card**: assets, KPI variants, refreshes, owner load. Nothing priced.
   (Gajus Z2)
4. **Self and company benchmark** instead of peers: no leak with 4 plants. (Gajus Z4)
5. ~~"REUSE, uncertified" + certification ticket~~: withdrawn, = Gajus's REUSE-with-conditions (pushed first).
6. **Per-provider timeouts.** (Margiris 15.2)
9. **Period disambiguation only when it is ambiguous**: "this quarter" in the first month of a quarter asks
   "Q4 so far (Oct) or last full quarter (Jul-Sep)?"; any other period word is applied without a question.
   (Gajus's RULE-ANSWER-at-Intent, refined)
7. **Aggregation as a governed field** with an "assumption" label on the receipt. (Martynas A3 / Gajus Z5)
8. **Lint containment ships with a one-click "use AST-xxxx instead"**, so a block always comes with a next step.
   (Margiris RULE-001)

## My ranked input for DECISION.md (build window ~21:15-02:00)
| Rank | Change | Effort | Owner | Source |
|---|---|---|---|---|
| 1 | `make demo` / `make ui` on the data pack (F3) + seeded data dir per demo (belt); approvals as a pending change set (the fix) | S, 20 min + S-M | Donatas (governance.py) | Gajus F3, Gajus attack, Donatas TL;DR 3 |
| 2 | Names -> ids at the Intent boundary + parity test on the novice path | S | Gajus | Gajus F1 |
| 3 | `Intent.period` -> month filters + calendar in `dim_month` + period on every card + RULE-ANSWER lint | M | Donatas (render/lint ask) + Martynas (model) | Donatas / Martynas A1 |
| 4 | One `existing_answers()` (containment), F2 full scan, lifecycle-aware ranking, Steward-born drafts earn no trust | M | Margiris | Margiris #1, Gajus F2, alternative 2 above |
| 5 | Circuit breaker + "AI paused" badge + DEMO_MODE text calls + warm all demo questions | S | Donatas (warm) + Margiris (llm) | Donatas opt 1, Margiris opt 3 |
| 6 | Ordered render blocks + one role cut + no silent drops | M | Donatas | Donatas top 3 #3 |
| 7 | Governance write side: owner pick-list, scope on CREATE, permission in approve, send back reaches the requester (on Gajus's shared inbox N4) | S-M | Donatas | Donatas, Gajus N4 |
| 8 | Decision hash vs view hash (one approval, role views) | M | Martynas | Martynas S2 |

Pitch line (the 0-to-1 to lead with): Margiris's **net-zero estate** for "build less", plus Martynas's
**governance page inside the PBIP** for "governed". Both are visible in one screen and one file, and neither needs
numbers we cannot defend.
