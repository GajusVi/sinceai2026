# BUILD PLAN: BI Steward for Bayer (Fri 6 Nov 22:00 to Sun 8 Nov 08:00)

One page to run the weekend from. Context: docs/challenge/ (brief, Panu's framework, data-pack traps).
Owners follow OWNERS / NOTES.md: **Gajus** product + pitch + docs · **Margiris** model, logic + proof ·
**Martynas** data · **Donatas** app, demo + submission. Each task: ID, owner, done-when. P0 = no demo without it.

## 0. What we are building (one sentence, lock in S1)
For a Bayer business user or BI lead, BI Steward turns a spoken or typed analytics request into one governed decision
(reuse, extend, consolidate, create or clarify) with cited evidence, and only builds a new dashboard spec when nothing
trustworthy exists, so the company gets fewer, owned, KPI-consistent dashboards.

```
voice/text ─▶ INTERVIEW (local or cloud LLM) ─▶ Intent ─▶ EVIDENCE ENGINE (code) ─▶ Decision + evidence cards
                 asks only what's missing         │            KPI ids, scope, usage, owner,      │
                                                  │            refresh, lineage, signals          ▼
                                    expert mode skips interview              human approve / reject ─▶ journal
                                                                             CREATE/EXTEND ─▶ DashboardSpec ─▶ preview + .PBIP skeleton
ORPHAN RESCUE: pick an asset ─▶ reverse-engineer into Intent ─▶ same engine        ESTATE HEALTH: retire / consolidate / migrate queue
```
Scoring weights we build against: 30% fit · 25% governance · 20% tech/AI · 15% usability (business AND IT) · 10% scale/demo.

## 1. Team sessions (everyone, timeboxed; output written to NOTES.md)
| ID | When | Session | Output |
|---|---|---|---|
| S1 | Fri 22:15-23:00 | **Logic lock** (agenda in section 2) | verdict table, thresholds, Intent fields, demo story, local-LLM decision |
| S2 | Sat 08:30-09:00 | Q&A prep | 5 questions for Panu (docs/challenge/05_SYNTHESIS.md), who goes (Gajus + Donatas) |
| S3 | Sat 12:00-12:30 | **Structure checkpoint** | eval v1 number, what works end to end, cut list |
| S4 | Sat 14:30-15:30 | Show Panu real outputs | his reaction on 3 decisions + 1 spec, adjustments |
| S5 | Sat 21:00-21:30 | Demo-path review | the exact 5-beat demo runs on one laptop |
| S6 | Sun 02:00 | **Code freeze** + dry run | tagged commit `demo-freeze`, only fixes after |
| S7 | Sun 07:00-07:45 | Submission review | page, video, README checked against brief section 07 |

## 2. S1 agenda: decide these together (proposals to accept or change)
1. **Verdicts for a question.** Proposal:
   | Verdict | Rule (all on approved KPI ids, never on names) |
   |---|---|
   | CLARIFY | unmapped terms > 0, or text vs metadata conflict, or no metric found → interview asks |
   | NOT_FEASIBLE | metric not in KPI catalog at all (e.g. "batch yield") → say so, offer nearest governed metric |
   | REUSE | best candidate: all requested canonical metrics via approved KPI ids, scope fits, trust ≥ 0.6, Power BI |
   | EXTEND | covers ≥ 50% incl. ≥ 1 requested metric; gaps are a metric on the same model, a breakdown, an owner, certification, or a variant KPI to swap to canonical |
   | CONSOLIDATE | ≥ 2 candidates with same product scope and KPI-set Jaccard ≥ 0.6 → keep the most trusted, retire the rest |
   | CREATE | nothing compatible; metrics exist in catalog + a certified/promoted semantic model → spec |
2. **Lifecycle flags on any candidate:** MIGRATE (Tableau + real usage, RULE-006), RETIRE (rule below), REASSIGN_OWNER (inactive/missing owner), FIX_REFRESH (model refresh failed/warning).
   **RETIRE candidate only if ALL hold** (all thresholds in steward/config.py, stated as assumptions in README):
   - *Old enough to judge:* created ≥ 3 months before as-of date; younger = "too new to judge", never flagged.
   - *Low use, relative not absolute:* average **monthly unique users since creation** in the bottom 20% of comparable assets
     (same asset type), AND < 10 users in each of the last 3 months. Count only months after created_date
     (the data pack has usage dated before creation for 218 of 400 rows on assets created from Apr 2026: ignore and flag as DQ).
   - *Nobody depends on it quietly:* 0 subscriptions in the last 3 months (77 of the 153 low-use assets have some),
     no downstream ASSET_TO_ASSET dependants (24 of them feed another asset), no high-criticality KPI (those go to HUMAN_REVIEW).
   - *Plus a reason beyond low use:* duplicate of a more trusted asset, or no active owner.
   Never automatic: recommend with evidence → owner/steward approves → archived and reversible for 30 days → removed.
   Why not "< 1,000 views": that number is just the empty gap in this synthetic data (153 assets < 750 views, none 750-2,000);
   it ignores asset age and time window and would not transfer to a real estate.
3. **Trust score:** certified 0.40 / promoted 0.25 · active owner 0.20 · model refresh healthy 0.25 / warning 0.10 · avg monthly unique users ≥ 50: 0.15, ≥ 10: 0.05 · minus 0.10 per open high-severity signal (floor 0).
4. **Scope rules (our assumptions, go in README).** Scope = the product_scope and market_scope *fields*, never the asset name (trap 18: 67 of 88 name suffixes contradict market_scope): asset with product "All Pharma" or market "Global" = has that breakdown; region asked (EMEA) needs Global or a region-level asset, a single-country asset does not cover it; month grain only (data is monthly Jan-Oct 2026).
5. **Never trust these columns as truth:** lifecycle_status, estimated_audience, Migration_Backlog path, request product_context (all shown to contradict usage/text). Use them as "claimed" vs our "observed".
6. **Intent fields** (Pydantic, contract between interview and engine): role, decision_supported, cadence, products[], markets[], regions[], metric_ids[] (canonical), unmapped_terms[], grain, comparison (target/forecast/prior), audience, conflicts[], confidence{field: 0-1}, mode (novice/expert/rescue).
7. **Interview stop rule:** all of products, markets, ≥ 1 metric, decision_supported filled with confidence ≥ 0.7, or 5 questions asked; expert mode asks only on conflicts.
8. **Local LLM decision:** Gajus's Intel Mac cannot run a useful local model. Proposal: interview runs on Ollama (small Gemma) on Donatas's M4 for the "raw words stay on device" story; everything else on Gemini Flash (free student credits, MLH Gemini tick). One env switch back to cloud.
9. **Demo story** (5 beats, docs/steward/demo-script.md rewritten): REQ-0001 conflict → consolidate Nubeqa duplicates → expert asks "Inventory Coverage Mgmt" → disambiguation → orphan AST-0091 rescue → one CREATE with spec + preview, approve, journal.

## 3. Contracts first (Fri 23:00-00:00): stub code everyone builds against
| ID | Owner (+ reviewer) | File | Done when |
|---|---|---|---|
| C1 | Martynas (+Margiris) | steward/models.py: `Artifact` gets platform, workspace_id, model_id, product_scope, market_scope, kpi_ids, endorsement, lifecycle_claimed, owner_status, usage (views/users by month), refresh_status, signals, data_quality, upstream/downstream ids | pydantic model merged, old fields kept or mapped |
| C2 | Gajus (+Margiris) | steward/intent.py: `Intent` (section 2.6) | merged; ParsedQuestion = Intent or adapter |
| C3 | Margiris (+Donatas) | steward/models.py `Decision` gains `evidence: list[Evidence]` (claim, rule_id, record_ids, value) + `flags` | merged; UI can render a fake one |
| C4 | Martynas (+Donatas) | steward/spec.py: `DashboardSpec` (name, entities, columns, grain, relationships, measures, pages, rationale, owner, kpi_ids, source_model_id) | merged with one hand-written example |

## 4. Workstreams

### Martynas: data (catalog from the data pack)
| ID | P | Task | Done when |
|---|---|---|---|
| D1 | P0 | `steward/catalog.py` loads the xlsx: Analytics_Assets + Owners + Asset_KPI_Map + Asset_Usage + Semantic_Models + Lineage_Edges + Governance_Signals + Data_Quality → 360 Artifacts | `Catalog.load()` returns 360, test asserts counts from docs/challenge/03_DATA_PACK.md |
| D2 | P0 | Metric dictionary: 18 canonical metrics from KPI_Catalog (canonical row = official), variants mapped with definition_status/approval_status/owner; **hand-write synonyms** per canonical metric (sales, revenue, GTN, OTIF, stock cover...) | `catalog/metrics.json` generated + synonyms reviewed by Gajus |
| D3 | P0 | Dimensions: products (7 + "All Pharma"), markets (14), regions (4 → markets rollup), grain = month | linking finds "Germany", "DE", "EMEA", "Nubeqa" |
| D4 | P0 | Retire the invented catalog: tests/bi_steward goldens move to data-pack records (with Margiris) | `make test` green on data pack only |
| D5 | P1 | Label hold-out with Margiris: 40 Business_Requests (4 per template) + 10 hand-written expert/edge requests, expected verdict + best asset + expected metrics | `eval/holdout_steward.jsonl` committed **before** threshold tuning |
| D6 | P1 | Spec renderer (after C4): `DashboardSpec` → Plotly preview from Product_Market_Monthly (synthetic numbers labelled) | preview renders for 3 specs |
| D7 | P2 | `.PBIP` skeleton writer: folder with report + semantic model definition files from the spec (label as skeleton) | folder created + zipped in UI; verify format in docs before claiming Power BI opens it |

### Margiris: logic, LLM plumbing, proof
| ID | P | Task | Done when |
|---|---|---|---|
| L1 | P0 | `steward/llm.py`: add an OpenAI-compatible client that reuses `backend/llm.py` / `backend/config.py` → Gemini and Ollama work with **no new install**, JSON validated, demo cache works | `make ask` shows provider gemini with the team .env |
| L2 | P0 | Matching by KPI id: metric counts only via the canonical approved KPI; variants → conflict card (replaces formula-string matching in linking.py / conflicts.py) | "Inventory Coverage Mgmt" yields KPI-018/019 conflict, canonical KPI-016 suggested |
| L3 | P0 | **No silent drops:** parser returns unmapped_terms; they count in the coverage denominator; any unmapped or text/metadata conflict → CLARIFY | REQ-0001 no longer returns REUSE |
| L4 | P0 | Coverage + trust on real fields (section 2.3-2.4), Tableau never REUSE; scope from fields only, name/scope mismatch → DQ flag (trap 18) | unit tests for 3 hand-picked assets |
| L5 | P0 | Verdict engine: REUSE/EXTEND/CONSOLIDATE/CREATE/CLARIFY/NOT_FEASIBLE + lifecycle flags; every reason carries rule_id + record ids (RULE-008) | Decision.evidence filled for every verdict |
| L6 | P1 | Health on real data: RETIRE rule from section 2.2 (age, relative monthly users, subscriptions, dependants), 21 null + 65 inactive owners, 16 certified-on-failed-refresh, duplicate clusters, Tableau re-triage vs Migration_Backlog | numbers match 03_DATA_PACK.md |
| L7 | P1 | Lineage impact: upstream model + downstream assets (ASSET_TO_ASSET, MODEL_TO_MODEL) for any RETIRE/CONSOLIDATE | "retiring X affects Y, Z" shown |
| L8 | P1 | **Eval** (`eval/eval_steward.py`): verdict accuracy, **false-REUSE rate** (headline), intent F1 (products/markets/metrics), confusion matrix, misses list → eval/results.json | first number at S3 |
| L9 | P1 | Semantic search: swap trigram embedder for fastembed (already installed) | top-3 hit rate on hold-out before/after |
| L10 | P2 | Headline numbers script: % of 150 requests resolved without a new dashboard, assets flagged, duplicate clusters | numbers computed, never typed by hand |

**"LLM training" = prompts + few-shot + eval, no fine-tuning.** No time, no labelled corpus, and judges score the
end-to-end workflow, not model complexity. Levers in order: (1) constrained outputs (ids from fixed lists only),
(2) few-shot examples from the 10 request templates, (3) temperature 0, (4) validator + rules fallback, (5) measure on hold-out
after every prompt change (`make eval`). Model choice per job: interview = small local or Gemini Flash; parsing = Gemini Flash;
explanation = Gemini Flash; verdict = **code only**.

### Gajus: product logic, interview brain, proof story, docs, pitch
| ID | P | Task | Done when |
|---|---|---|---|
| G1 | P0 | Run S1; write decisions + thresholds into NOTES.md and steward/config.py comments | S1 output in NOTES.md by 23:00 |
| G2 | P0 | Interview prompt `prompts/interview.yaml`: situation questions, never spec questions, plain-language KPI offers, conflict question (REQ-0001), stop rule, outputs Intent JSON | 3 scripted conversations produce valid Intents |
| G3 | P0 | Question bank by persona (supply planner, market-access lead, finance controller, BI lead): 5 questions each | in prompts/ as few-shot |
| G4 | P1 | Orphan-rescue narrative + AST-0091 walkthrough (with Donatas) | script approved by team |
| G5 | P1 | Euro case: formula volume × hours × rate, every input labelled as assumption or data-pack number | one slide line + README section |
| G6 | P0 | README / architecture note covering brief section 07: data assumptions, AI approach, governance controls, enterprise-BI integration (Power BI/Fabric scanner APIs, Purview), limitations | README reviewed at S7 |
| G7 | P1 | Pitch (4 min) + /judge-qa prep (investor, ecosystem, AI-agents professor) | rehearsed twice Sun 06:00 |
| G8 | P1 | S2/S4 with Panu: questions, then show outputs, log answers in NOTES.md | answers logged |

### Donatas: app, voice, demo, submission
| ID | P | Task | Done when |
|---|---|---|---|
| A1 | P0 | Ask tab becomes a chat (`st.chat_input`): interview turns, then decision; expert toggle skips to direct parse | novice + expert paths run end to end |
| A2 | P0 | Decision screen: verdict, evidence cards with rule id + record ids, "claimed vs observed" for lifecycle/audience, approve/reject with reason | outsider understands in 10 s |
| A3 | P0 | KPI disambiguation card (his concern #1): canonical vs variants, status, owner, default canonical, exception needs a reason | shown for "Inventory Coverage Mgmt" |
| A4 | P1 | Orphan rescue tab: pick asset (default AST-0091) → reverse-engineered Intent + decision | AST-0091 shows inactive owner, refresh warning, recommendation |
| A5 | P1 | Spec + preview panel for CREATE/EXTEND (after C4, D6): spec table, preview chart, download .PBIP skeleton | approve writes spec to journal |
| A6 | P1 | Voice: `st.audio_input` → transcript (local Whisper on M4 if it installs cleanly, else Gemini audio) → editable text → interview | voice question reaches the interview; text always works |
| A7 | P0 | Demo mode: `make demo` replays cached LLM outputs (reuse demo/cache via L1); "Reset demo" clears data/steward/ | demo runs twice offline |
| A8 | P1 | Health tab on real data (after L6): estate queue with retire/consolidate/migrate + approve | numbers visible for pitch |
| A9 | P0 | Video (~2 min, English narration, captions, screen recording, label anything mocked, no invented numbers), screenshots, sinceai.app page | uploaded by Sun 08:00 |

## 5. Clock (Helsinki time) and checkpoints
| When | Milestone | Must be true |
|---|---|---|
| Fri 23:00 | S1 done | NOTES.md has verdict table, Intent fields, demo story |
| Fri 24:00 | Contracts C1-C4 merged | everyone builds against stubs |
| Sat 03:00 | **Core on real data** | D1-D4, L1-L3 merged; REQ-0001 → CLARIFY; app runs on data pack. Sleep 03:00-08:00 (keep one phone on) |
| Sat 09:00 | Panu Q&A | G8 |
| Sat 12:00 | **S3 structure checkpoint** | eval v1 number, chat interview v1, evidence cards; cut list decided |
| Sat 15:30 | S4 done | Panu has seen real decisions + a spec |
| Sat 21:00 | Feature complete | A1-A5, L5-L8, D5-D6, G2-G3 merged |
| Sun 02:00 | **Freeze** (tag `demo-freeze`) | demo runs offline twice, eval v2 committed |
| Sun 06:00 | Video, README, page drafted | A9, G6 |
| Sun 08:00 | **Submit** (hard deadline 10:00) | /ship-check PASS |

## 6. Cut order if behind (decide at S3)
Cut first → last: D7 .PBIP skeleton · A6 voice · local LLM (use Gemini) · L9 fastembed · A8 health tab polish · L7 lineage.
Never cut: L3 no-silent-drops, L2 KPI ids, A2 evidence + approve, L8 eval number, A7 demo mode, G6 README.

## 7. Rules that keep four Claude Codes from colliding
- `git pull --rebase` before work and before push; small commits; tests green before push (pre-push runs them).
- Contracts (models.py, intent.py, spec.py) change only with the owner + one reviewer.
- Golden/hold-out verdict changes go in the same commit as the rule change, with the reason.
- New files: add an OWNERS line in S1 (proposed: intent.py + prompts/interview.yaml gajus; decision/, search/, llm.py, health.py, eval/ margiris; catalog.py, models.py, spec.py, catalog/ martynas; frontend/, demo/ donatas).
