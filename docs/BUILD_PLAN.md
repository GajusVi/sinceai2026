# BUILD PLAN v2: the governed Dashboard Factory (Sat 7 Nov 03:30 → Sun 8 Nov 08:00)

**Now:** night shift (section 6.1): Gajus + Margiris build a rough full draft by 08:30. Martynas + Donatas start at 08:00 with docs/tasks/<name>.md (review + take back + harden).

**v2 change (Gajus, Sat 03:10):** the end product is a **governed, rendered dashboard plus a .PBIP project**, for every verdict.
v1 ended at the verdict, with spec + preview as P1 and .PBIP as the first cut. That missed Panu's framework (Prompt in, .PBIP out).
Everything built so far stays (interview, intent, KPI ids, evidence engine, trust, approval, journal, orphan rescue). It becomes the
first half of one flow that ends in a dashboard. The S1 decisions (section 11) are unchanged.

Owners follow OWNERS / NOTES.md: **Gajus** product, spec builder, docs, pitch · **Margiris** verdict engine, lint gate, eval ·
**Martynas** data, semantic layer, spec contract, .PBIP · **Donatas** renderer, app, demo, submission.
Tell your Claude Code: **"Do docs/tasks/<name>.md. Read CLAUDE.md and docs/BUILD_PLAN.md sections 0-6 first."**

## 0. What we build (one sentence)
For a Bayer business user or BI lead, BI Steward turns a spoken or typed analytics request into one governed decision and the
**dashboard that decision implies**: the existing one (REUSE), its next version (EXTEND), the merged one (CONSOLIDATE), its Power BI
successor (MIGRATE) or a new one (CREATE). Each is rendered on governed KPIs, checked against RULE-001..008, approved by a human and
exported as a .PBIP project. So the company gets fewer, owned, KPI-consistent dashboards, and every one it does get is built right.

```
 W0 ENTRY            W1 INTERVIEW        W2 KPI RESOLUTION     W3 FEASIBILITY         W4 EVIDENCE + VERDICT
 typed / voice  ──▶  /grill-me (LLM) ──▶ words → canonical ──▶ can governed data  ──▶ /explore: search, coverage,
 request row         situation Qs        KPI ids; variants      answer it? measure      trust, scope, lineage, usage
 orphan asset        stop rule           → disambiguation       bindings, scope,        → REUSE | EXTEND | CONSOLIDATE
 estate finding      ◀── G1: intent clear ◀── G2: KPIs governed  ◀── G3: buildable ──┐    | CREATE (+ MIGRATE/RETIRE/
        ▲                                                         (else NOT_FEASIBLE   │    REASSIGN/FIX_REFRESH flags)
        │                                                          + nearest offer) ───┘    | CLARIFY → back to W1
        │
        │   W5 SPEC (/to-spec)       W6 LINT GATE           W7 RENDER             W8 HUMAN GATE        W9 PUBLISH
        └── verdict → DashboardSpec ─▶ RULE-001..008 +   ─▶ deterministic      ─▶ approve / reject  ─▶ catalog version,
            per branch (section 2);     FOCUS + DATA rules   Python: KPI cards,    with reason;         journal (spec hash,
            LLM proposes layout from    pass / warn / block  trend, breakdown,     block = no approve    lint, model, prompt),
            a fixed menu, code checks   on the SPEC itself    exceptions, filters,                      .PBIP zip (TMDL +
                                                              governance footer                         PBIR), lineage edges
 W10 LIFECYCLE LOOP: estate health (retire / consolidate / migrate / reassign) feeds W5-W9 too: a consolidation produces the merged dashboard.
```
Yellow (LLM) steps: W1 interview, W5 layout proposal + titles, explanation text. Everything else is deterministic Python.
Verdict, feasibility, lint and render are code: same input, same output, testable (Panu: "the final render can be plain code").

## 1. The stages, gates and owners
| Stage | What happens | Output | Gate (blocks the next stage) | Owner | Status |
|---|---|---|---|---|---|
| W0 Entry | 4 doors: chat (novice/expert), Business_Requests row with its metadata, orphan asset, estate finding | text + context | – | Donatas (UI), Gajus (requests.py) | chat + rescue tab done; estate door new |
| W1 Interview | situation questions, conflict question, stop rule | `Intent` | **G1** intent clear: stop rule met, no open blocker conflict | Gajus | done (Gemini + Aitta) |
| W2 KPI resolution | metric words → canonical approved KPI ids; variants → disambiguation card | `Intent.metric_ids` + conflicts | **G2** every KPI canonical+approved, or exception with reason | Margiris (linking), Donatas (card A3) | ids done; card open |
| W3 Feasibility | each KPI bound to a measure in the semantic layer? products/markets present in the facts? month grain? | `Feasibility` | **G3** ≥ 1 buildable measure; else NOT_FEASIBLE + nearest governed alternative, loop to W1 | Martynas | **new** |
| W4 Evidence + verdict | search, coverage, trust 2.3, scope 2.4, usage, lineage, signals | `Decision` + evidence + flags | CLARIFY → W1 | Margiris | REUSE/EXTEND/CREATE/CLARIFY done; CONSOLIDATE, NOT_FEASIBLE, flags open (L5) |
| W5 Spec | per-verdict spec builder (section 2) + layout rules (section 5); LLM proposes layout from a fixed menu, code validates, template fallback | `DashboardSpec` v2 | – | Gajus | **new** |
| W6 Lint gate | rules on the spec itself (section 5.2) | `LintResult[]` on the spec | any `block` → approve disabled | Margiris | **new** |
| W7 Render | deterministic: spec + semantic frames + filters → dashboard | `RenderedDashboard` | – | Donatas | **new** |
| W8 Human gate | approve / reject with reason; owner required; exception reasons | journal entry | – | Donatas (governance.py) | approve/reject done; spec link new |
| W9 Publish | catalog version (EXTEND v{N}, CREATE draft, CONSOLIDATE keeper + retire list), journal with spec hash + lint + model/prompt, .PBIP zip, lineage edges | files + journal | – | Martynas (.PBIP), Donatas (journal) | **new** |
| W10 Lifecycle | estate queue items run W5-W9 | dashboards for consolidations/migrations | – | Margiris (L6/L7), Donatas (A8) | health done; queue → spec new |

## 2. Verdict → dashboard (what W5 builds for each branch)
| Verdict / flag | Base | What the spec contains | What the human approves | Published as |
|---|---|---|---|---|
| **REUSE** | the matching asset | `spec_from_asset(best)`: its canonical KPIs, scope, model; filtered to the question | "Open this" (nothing new is built) | journal only; the render shows the existing dashboard on governed data |
| **EXTEND** | best compatible asset | base spec + `changes`: add missing measures / breakdowns, swap variant KPIs to canonical (RULE-002), owner/certify/refresh fixes | the new version, with a **diff** (new elements highlighted) | asset v{N+1}; old version `superseded`; .PBIP |
| **CONSOLIDATE** | the most trusted asset of the duplicate cluster | union of the cluster's canonical KPIs, `merge_from` changes; retire list with downstream impact (RULE-004) | keeper version + each retirement (30-day reversible) | keeper v{N+1}; others → retire queue; .PBIP |
| **CREATE** | none | from Intent + Feasibility on the best governed semantic model (Power BI, certified/promoted, refresh healthy, scope fits: 15 such models in the pack) | the new dashboard; owner mandatory (default = model owner, editable) | draft asset + lineage edge model→asset; .PBIP |
| **MIGRATE** flag (Tableau best) | the Tableau asset | Power BI spec of the *rationalised* asset: canonical KPIs only, duplicates merged first, target model from Migration_Backlog only if healthy (RULE-006) | the Power BI successor | new PBI asset; Tableau → retire queue; .PBIP |
| **RESCUE** (orphan door) | the orphan asset | `spec_from_asset(orphan)` + REASSIGN_OWNER successor + canonical swaps | successor accepts; repaired version | v{N+1} with new owner; .PBIP |
| **NOT_FEASIBLE** | – | no spec. Shows which KPIs are governed but have no source data (e.g. KPI-034 Gross-to-Net) + the nearest buildable alternative | user accepts the alternative (→ W1) or files a data request (journaled) | journal |
| **CLARIFY** | – | no spec; back to W1 with the blocking terms/conflicts | – | – |

## 3. Contracts v2 (additive, every new field defaulted; all tests stay green)
**C5 `steward/spec.py` (owner Martynas; drafted tonight by Gajus as N1, pushed by 04:00 with a fixture `tests/bi_steward/fixtures/spec_req0001.json`)**
```python
class Measure(BaseModel):            # existing fields kept: name, kpi_id, expression, format
    unit: str = ""                   # EUR | % | weeks | units | index
    source: str = ""                 # "fact_pmm.net_sales_m_eur_syn" or "derived"
    aggregation: str = "sum"         # sum | avg | ratio | derived
    definition_status: str = "canonical"
    feasible: bool = True
    gap_reason: str = ""             # "KPI-034 is governed but no governed model holds its source data"
class Visual(BaseModel):             # existing: type, title, measures, dimension
    purpose: str = ""                # the decision it supports, one line
    comparison: str | None = None    # measure name shown against it (forecast, prior month)
    threshold: float | None = None   # for exception tables / colouring
class Page(BaseModel):               # existing: name, visuals
    purpose: str = ""
class SpecChange(BaseModel):
    kind: str                        # add_measure | add_breakdown | swap_variant | merge_from | assign_owner | migrate_platform | remove_visual
    detail: str
    record_ids: list[str] = []
class LintResult(BaseModel):
    rule_id: str                     # RULE-001..008 | FOCUS | DATA
    status: str                      # pass | warn | block
    message: str
    record_ids: list[str] = []
class DashboardSpec(BaseModel):      # existing fields kept
    verdict: str = ""
    change_type: str = "create"      # reuse | extend | consolidate | create | migrate | rescue
    base_asset_ids: list[str] = []
    version: int = 1
    changes: list[SpecChange] = []
    audience: str = ""
    decision_supported: str = ""
    cadence: str = ""
    platform: str = "Power BI"
    lint: list[LintResult] = []
    data_label: str = "Synthetic data from the Bayer SinceAI 2026 data pack, not Bayer performance"
    provenance: dict[str, str] = {}  # layout_source llm|template, model, prompt file, spec_hash
```
**C6 `catalog/bayer/measures.json` + `steward/semantic.py` (owner Martynas; draft N2 by Gajus, 05:00):** the governed semantic layer (section 4).
`load_frames() -> dict[str, pd.DataFrame]` (cached), `star_schema() -> (entities, columns, relationships)`,
`feasibility(intent) -> Feasibility(buildable: list[Measure], gaps: list[Measure], scope_ok: bool, nearest: list[str])`.
**C7 `steward/specbuild.py` (Gajus; N3 tonight: REUSE/EXTEND/CREATE):** `build_spec(decision, intent, catalog, feasibility) -> DashboardSpec | None` (None for CLARIFY/NOT_FEASIBLE), `spec_from_asset(asset)`.
**C8 `steward/lint.py` (Margiris; N5 tonight):** `lint(spec, catalog) -> list[LintResult]`; `can_approve(spec) = no block`.
**C9 `steward/render.py` (owner Donatas; draft N4 by Gajus tonight):** `render(spec, frames, filters) -> RenderedDashboard(cards, figures, tables, footer, gaps)`; Plotly (installed), no new packages.
**C10 `steward/pbip.py` (owner Martynas; TMDL draft N7 by Margiris tonight, report half Saturday):** `export_pbip(spec, frames, out_dir) -> Path` (zip). Built from templates saved by Power BI Desktop (section 6, M4).
**Pipeline:** `Steward.ask(...)` result gains `spec: DashboardSpec | None`; `Steward.build(decision, intent)` runs W3, W5, W6. Shared file `steward/pipeline.py`: Gajus wires it.

## 4. Semantic layer: what the governed data can show (W3)
Star schema built from the data pack (all synthetic, labelled on every render):
`fact_pmm` Product_Market_Monthly (product × market × month, 980 rows) · `fact_supply` Supply_Operations · `fact_access` Market_Access ·
`fact_launch` Launch_Milestones · `fact_usage` Asset_Usage + Analytics_Assets (BI-governance KPIs) · `dim_product` (7) · `dim_market` (14 → 4 regions) · `dim_month` (Jan-Oct 2026).
Relationships: every fact many-to-one to dim_product, dim_market, dim_month on product_id / market_id / month.

| Canonical KPI | Binding (Martynas confirms each) |
|---|---|
| KPI-001 Net Sales | fact_pmm.net_sales_m_eur_syn, sum |
| KPI-004 Net Sales Growth | derived: net sales vs prior month |
| KPI-006 Demand Forecast Accuracy | fact_supply.forecast_accuracy_pct_syn, avg |
| KPI-010 Demand Forecast Bias | derived: (net sales − forecast) / forecast |
| KPI-014 Units Shipped | fact_pmm.units_shipped_syn, sum |
| KPI-016 Inventory Coverage | fact_pmm.inventory_weeks_syn, avg |
| KPI-020 On-Time In-Full | fact_pmm.otif_pct_syn, avg |
| KPI-027 Market Access Coverage | fact_pmm.market_access_coverage_pct_syn, avg |
| KPI-031 Reimbursement Status Coverage | fact_access: share of markets "listed" |
| KPI-042 Forecast Variance | fact_pmm net sales − forecast (EUR), plus forecast_variance_pct |
| KPI-051 Report Adoption | fact_usage unique users |
| KPI-054 Certified Asset Share | Analytics_Assets endorsement share |
| KPI-023 Launch Adoption Index | **gap** (milestone table only, no index values) |
| KPI-034 Gross-to-Net, KPI-037 Operating Contribution, KPI-039 Budget Variance, KPI-046 Commercial Reach, KPI-049 Digital Engagement | **gap**: governed KPI, no source data. NOT_FEASIBLE for that measure (Panu's feedback loop) |
So 12 of 18 bind. Request template 2 ("net sales, gross-to-net and budget variance", 20 rows) is the demo of a partial feasibility gap.
Data-quality rules carried in (trap 14): zero-sales rows with null variance are excluded from averages and shown as a DQ note, not hidden.

## 5. Dashboard design rules (W5) and the lint gate (W6)
### 5.1 Layout (Panu: "the fixed set of KPIs the shift sees when they walk in"; human factors in scope)
- **One page** by default: "What needs attention". At most 4 KPI cards (headline canonical measures, each against its comparison:
  forecast, prior month, or threshold), 1 trend (headline measure by month with comparison), 1 breakdown (by the intent's "by" dimension:
  market, region or product), 1 exceptions table (rows past a threshold: OTIF < 90%, inventory < 4 weeks, |forecast variance| > 10%).
- A second "Detail" page only when more than 4 measures are requested. Max 7 visuals per page, 2 pages.
- Titles in business language, answer first ("Nubeqa net sales vs forecast, by country"). No jargon, no KPI ids in titles (ids in the footer).
- Governance footer on every page: KPI ids + status, source model id + endorsement + refresh, owner, version, data label.
- **LLM role (W5):** picks the headline measure, the comparison and the exception threshold from a fixed menu, and writes the name,
  titles and rationale (`prompts/to_spec.yaml`). Code rejects anything outside the menu or any number in the text. Template layout on failure.
### 5.2 Lint rules on the spec (block = approve disabled)
| Rule | Check | Fail |
|---|---|---|
| RULE-001 Reuse before build | CREATE: no compatible asset with canonical-KPI Jaccard ≥ 0.6 on the same scope | block |
| RULE-002 Canonical KPI first | every measure canonical + approved, or an exception with reason | block |
| RULE-003 Owner required | owner set and active | block |
| RULE-004 Lineage required | source_model_id set; CONSOLIDATE/RETIRE list downstream impact | block |
| RULE-005 High reach requires trust | high audience → model certified/promoted; refresh failed → block, warning → warn | warn / block |
| RULE-006 Do not migrate waste | MIGRATE: canonical only, duplicates merged, no low-use 1:1 copy | block |
| RULE-007 AI-ready semantics | every visual's measures bound with an expression; month date axis; business names | warn |
| RULE-008 Explain every action | every SpecChange carries record ids | block |
| FOCUS | ≤ 7 visuals per page, ≤ 2 pages, ≤ 4 KPI cards | warn |
| DATA | an infeasible measure is rendered only as a labelled gap, never with numbers | block |

## 6. Timeline: rough full draft tonight, harden and design on Saturday
**Goal by 08:30:** a rough but complete W0→W9 draft that runs on the data pack, so Panu sees a real dashboard at the 09:00 Q&A and
Saturday is spent on his feedback, quality and design, not on first builds. Martynas and Donatas are offline until 08:00, so tonight
**Gajus and Margiris build drafts of every new module, including files the others own**. Those files are handed back at 08:00
(OWNERS has the NIGHT lines; the owner reviews, keeps or rewrites). Rough is fine: plain layout, template text, few tests. It must run.

### 6.1 Night shift (Sat 03:30 → 08:30)
Two tracks, no shared files, so the two Claude Codes never collide. Track A alone already gives an end-to-end draft;
Track B adds the lint gate, the missing verdicts and the export. **If Margiris has not confirmed by 03:45, Gajus runs N5 after N4
and N6/N7 move to the morning owners.**

| Order | Task | Track A: Gajus | Track B: Margiris | Push by | Done when |
|---|---|---|---|---|---|
| 1 | **N1** spec.py v2 (section 3, C5, additive) + fixture `tests/bi_steward/fixtures/spec_req0001.json` | ✔ (night owner of spec.py) | | 04:00 | fixture validates, tests green, `say all done` |
| 2 | **N2** measures.json + semantic.py: load_frames, star_schema, feasibility (section 4) | ✔ | | 05:00 | REQ-0001 = 3 buildable; template 2 = 1 buildable + 2 gaps |
| 3 | **N3** specbuild.py: REUSE, EXTEND, CREATE with the template layout (5.1) + `Steward.build()` in pipeline.py | ✔ | | 06:15 | specs for the 3 cases in a test |
| 4 | **N4** render.py + dashboard panel in the Ask flow: cards, line, bar, exceptions table, gap cards, footer; lint panel; approve writes spec hash + lint to the journal; spec JSON download | ✔ (night owner of frontend/steward_app.py) | | 08:00 | REQ-0001 W0→W8 on screen in `make bayer` |
| 1 | **N5** lint.py, all rules of 5.2 (simple checks first) | | ✔ starts on the fixture at 04:00 | 06:00 | pass + fail test per rule |
| 2 | **N6** L5: CONSOLIDATE + NOT_FEASIBLE (uses semantic.feasibility from N2) | | ✔ | 07:30 | template 2 → NOT_FEASIBLE gaps as Evidence; a duplicate cluster → CONSOLIDATE |
| 3 | **N7** pbip.py rough: TMDL semantic model (tables, measures, relationships) + spec JSON in a zip; report half is Martynas's in the morning | | ✔ (night owner of pbip.py) | 08:00 | zip downloads from the app; folder layout matches the Microsoft PBIP docs |
| 08:15 | **Handover**: each pushes, `tools/coord.py status`, 3 lines in NOTES.md (done / rough / missing) | ✔ | ✔ | | |

Until N1 lands, Margiris codes N5 against the contract in section 3 (field names are final). Until N2 lands, N6 uses CREATE logic only.

### 6.2 Saturday (feedback, hardening, design)
| Time | Gajus | Margiris | Martynas | Donatas |
|---|---|---|---|---|
| 08:00-09:00 | S2; demo the draft to the team; Panu questions incl. new Q2 | sleep or N-task leftovers | **review** N1/N2 (bindings vs xlsx, contract), take back spec.py, semantic.py, pbip.py | **review** N4, take back frontend + render.py |
| 09:00-12:00 | **Panu Q&A with the running draft** (with Donatas); log feedback | lint/verdict hardening (L5 flags, L11 edge cases) | M3 Desktop templates → M4 report half of .PBIP, open in Desktop | R2 polish: filters, EXTEND diff badges, layout design |
| 12:00 | **S3**: apply Panu's feedback list; cut list | | | |
| 12:00-21:00 | G9 rest: CONSOLIDATE/MIGRATE/RESCUE specs; G10 LLM layout; G11 numbers; README | L8 eval v1 (lint pass rate, dashboards avoided), L6/L7 | M4 verified in Desktop or 18:00 fallback; M5 labels | R3 Dashboards tab, estate door, design pass, demo cache on Gemini |
| 14:30 | **S4: Panu sees the improved version** | | | |
| 21:00 | **S5 demo-path review** · Sun 02:00 freeze · 06:00 video + README · 08:00 submit | | | |

**New Q2 for Panu (09:00):** "We render the dashboard deterministically from a spec and export a .PBIP (TMDL model + PBIR report). Do you
want to see it open in Power BI Desktop, or are the spec, the rendered preview and the files enough?" Log the answer in NOTES.md; it decides M4 effort.

## 7. Saturday task list per person (after the night draft; done-when)
| ID | P | Owner | Task | Done when |
|---|---|---|---|---|
| M1 | P0 | Martynas | review N1 spec contract + N2 measures.json bindings against the xlsx; fix or confirm | NOTES line "contract + bindings reviewed" by 09:30 |
| M3 | P0 | Martynas | Power BI Desktop (free, Windows): enable PBIP, TMDL and PBIR preview features; save templates: empty project + one report with one card, one line, one bar, one table on a CSV | `templates/pbip/` committed |
| M4 | P0 | Martynas | pbip.py: add the PBIR report half from the templates to Margiris's TMDL draft; open in Desktop | screenshot in submission/; fallback at 18:00 below |
| M5 | P1 | Martynas (+Margiris) | 20 hold-out rows with expected verdict + best asset | committed before tuning |
| G9 | P0 | Gajus | specbuild: CONSOLIDATE, MIGRATE, RESCUE branches on top of the night's REUSE/EXTEND/CREATE | 6 cases in tests |
| G10 | P1 | Gajus | prompts/to_spec.yaml + validator (menu-only, no numbers) | LLM layout passes lint on 3 cases; template fallback tested |
| G11 | P1 | Gajus | headline numbers from code over 150 requests | numbers in README/pitch, script committed |
| G6 | P0 | Gajus | README (brief section 07) incl. the factory, assumptions, lint rules, PBIP status; swap the herbicide example | reviewed at S7 |
| L5 | P0 | Margiris | remaining flags MIGRATE/RETIRE/REASSIGN/FIX_REFRESH with evidence ids; batch-yield known_gap removed | goldens green |
| L11 | P0 | Margiris | harden lint (RULE-001 Jaccard on real search, RULE-004 with lineage impact) | edge-case tests |
| L8 | P0 | Margiris | eval: verdict accuracy, false-REUSE rate, **spec lint pass rate, dashboards avoided** | eval/results.json at S3 (v1) and freeze (v2) |
| L6/L7 | P1 | Margiris | retire rule 2.2, lineage impact for CONSOLIDATE/RETIRE | numbers match 03_DATA_PACK.md |
| R2 | P0 | Donatas | dashboard panel polish: filters, EXTEND diff highlighting, lint panel (block disables approve), design | outsider understands it in 10 s |
| R3 | P1 | Donatas | Dashboards tab (approved specs), estate door → spec, .PBIP download, demo cache warm on Gemini | demo runs offline twice |
| A2/A3 | P0 | Donatas | evidence cards on the real engine, KPI disambiguation card | as v1 |
| A9 | P0 | Donatas | video (≈2 min) shows a rendered dashboard and the .PBIP | uploaded by 08:00 Sun |

**PBIP fallback (decide Sat 18:00):** if the export does not open in Desktop, ship the semantic model only (TMDL) plus the
spec JSON and the rendered preview, labelled "skeleton, not verified in Desktop". Never claim it opens unless someone opened it.

## 8. Demo story (5 beats, replaces S1 item 9)
1. **REQ-0001 arrives** with its form: the text says global Nubeqa, the form says Beyonttra/EMEA → interview asks one situation question and the conflict question → Intent.
2. **KPI resolution**: "forecast variance" → canonical KPI-042; a variant on the candidate asset is shown and swapped.
3. **Reuse before build**: evidence cards; verdict EXTEND on an existing asset (record ids, trust, owner, usage), not a new dashboard.
4. **The dashboard**: the extended version renders with the new elements highlighted, the lint gate passes, approve → v{N+1}, journal, .PBIP downloaded.
5. **The estate**: "of 150 requests, X% need no new dashboard" (from code); one consolidation renders the merged dashboard with its retire list;
   orphan AST-0091 gets a successor and a repaired version. Template 2 shows the honest gap: Gross-to-Net is governed but has no data → NOT_FEASIBLE for that measure.

## 9. Cut order if behind (decide at S3)
Cut first → last: A6 voice · L9 fastembed · G10 LLM layout (template layout stays) · R3 Dashboards tab · RESCUE/MIGRATE spec branches (verdict stays) · M4 report half of .PBIP (keep TMDL model).
**Never cut:** W5 spec for REUSE/EXTEND/CREATE, W6 lint gate, W7 render, W8 approval with spec in the journal, L3 no-silent-drops, L2 KPI ids, L8 eval number, A7 demo mode, G6 README.

## 10. Sessions (everyone, timeboxed; output in NOTES.md)
| ID | When | Session | Output |
|---|---|---|---|
| S2 | Sat 08:30-09:00 | Q&A prep | Panu questions incl. new Q2 |
| S3 | Sat 12:00-12:30 | **Structure checkpoint** | REQ-0001 W0→W7 on screen, eval v1, cut list |
| S4 | Sat 14:30-15:30 | Show Panu | rendered dashboard + spec + lint + .PBIP; his reaction logged |
| S5 | Sat 21:00-21:30 | Demo-path review | section 8 runs offline on one laptop |
| S6 | Sun 02:00 | **Code freeze** + dry run | tag `demo-freeze` |
| S7 | Sun 07:00-07:45 | Submission review | page, video, README vs brief section 07 |

## 11. S1 decisions (locked Fri 23:45; still valid)
1. **Verdicts for a question.** Proposal:
   | Verdict | Rule (all on approved KPI ids, never on names) |
   |---|---|
   | CLARIFY | unmapped terms > 0, or text vs metadata conflict, or no metric found → interview asks |
   | NOT_FEASIBLE | metric not in KPI catalog at all (e.g. "batch yield") → say so, offer nearest governed metric |
   | REUSE | best candidate: all requested canonical metrics via approved KPI ids, scope fits, trust ≥ 0.6, Power BI |
   | EXTEND | covers ≥ 50% incl. ≥ 1 requested metric; gaps are a metric on the same model, a breakdown, an owner, certification, or a variant KPI to swap to canonical |
   | CONSOLIDATE | ≥ 2 candidates with same product scope and KPI-set Jaccard ≥ 0.6 → keep the most trusted, retire the rest |
   | CREATE | nothing compatible; metrics exist in catalog + a certified/promoted semantic model → spec |
2. **Lifecycle flags on any candidate:** MIGRATE (Tableau + real usage, RULE-006), RETIRE (rule below), REASSIGN_OWNER (rule below), FIX_REFRESH (model refresh failed/warning).
   **Ownership = role + person, so leavers do not create orphans** (Owners sheet has role, scope, status; RULE-003).
   Owner inactive or missing → REASSIGN_OWNER with a proposed successor, resolved in this order:
   - *Same role, same scope, active* → propose that person (23 of the 65 inactive-owner assets). Successor must accept.
   - *Same role, other scope, active* → list them, steward picks (21 assets).
   - *Role vacant* (e.g. every Reporting Lead is inactive) → escalate to the workspace's BI Platform Owner and report
     "role vacant" as an estate finding (21 assets). The 21 assets with no owner_id at all also go to the BI Platform Owner.
   Never auto-assigned: the proposed person approves in the UI, the change is journaled.
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
3. **Trust score:** certified 0.40 (admin-authorised reviewer checked it) / promoted 0.25 (author vouches for it) · accountable owner: active person 0.20, inactive but role still staffed 0.10, role vacant or no owner 0 · model refresh healthy 0.25 / warning 0.10 · avg monthly unique users ≥ 50: 0.15, ≥ 10: 0.05 · minus 0.10 per open high-severity signal (floor 0).
4. **Scope rules (our assumptions, go in README).** Scope = the product_scope and market_scope *fields*, never the asset name (trap 18: 67 of 88 name suffixes contradict market_scope): asset with product "All Pharma" or market "Global" = has that breakdown; region asked (EMEA) needs Global or a region-level asset, a single-country asset does not cover it; month grain only (data is monthly Jan-Oct 2026).
5. **Never trust these columns as truth:** lifecycle_status, estimated_audience, Migration_Backlog path, request product_context (all shown to contradict usage/text). Use them as "claimed" vs our "observed".
6. **Intent fields** (Pydantic, contract between interview and engine): role, decision_supported, cadence, products[], markets[], regions[], metric_ids[] (canonical), unmapped_terms[], grain, comparison (target/forecast/prior), audience, conflicts[], confidence{field: 0-1}, mode (novice/expert/rescue).
7. **Interview stop rule:** all of products, markets, ≥ 1 metric, decision_supported filled with confidence ≥ 0.7, or 5 questions asked; expert mode asks only on conflicts.
8. **Local LLM decision:** Gajus's Intel Mac cannot run a useful local model. Proposal: interview runs on Ollama (small Gemma) on Donatas's M4 for the "raw words stay on device" story; everything else on Gemini Flash (free student credits, MLH Gemini tick). One env switch back to cloud.
9. **Demo story:** replaced by section 8 (v2).

## 12. Rules that keep four Claude Codes from colliding
- `git pull --rebase` before work and before push; small commits; tests green before push (pre-push runs them).
- Contracts (models.py, intent.py, spec.py) change only with the owner + one reviewer.
- Golden/hold-out verdict changes go in the same commit as the rule change, with the reason.
- New files: add an OWNERS line in S1 (proposed: intent.py + prompts/interview.yaml gajus; decision/, search/, llm.py, health.py, eval/ margiris; catalog.py, models.py, spec.py, catalog/ martynas; frontend/, demo/ donatas).
- v2 new files (OWNERS updated): steward/semantic.py, steward/pbip.py, catalog/bayer/measures.json, templates/pbip/ martynas; steward/specbuild.py, prompts/to_spec.yaml gajus; steward/lint.py margiris; steward/render.py donatas.
