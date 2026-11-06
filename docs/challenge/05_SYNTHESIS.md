# 05 Synthesis: what to build and why

## The core tension (resolve it, don't pick a side)
- **Written brief + data pack** = governance: reuse / consolidate / migrate / retire existing BI before building. No manufacturing data at all.
- **Panu's talk + slide** = a build factory: vague prompt -> grill-me -> intent -> evidence -> spec -> .PBIP, shop-floor KPIs.
- Scoring is 55% fit + governance. A pure "prompt-to-dashboard generator" would *increase* sprawl and lose on the title itself.
- **Resolution:** run his pipeline, but make /explore a **reuse-before-build gate**. Most requests should end in
  "use this existing certified report" or "consolidate these 3"; only true gaps reach /to-spec and render.
  One sentence pitch: *"Every request goes through an analyst agent that defaults to NOT building."*

## Product concept (working name: Build-Less Gate)
```
Business request (free text)
 1. /grill-me  (LLM)          non-technical interview: role, decision, cadence, scope; flags text-vs-metadata conflicts
 2. Intent     (state)        product, market, canonical metrics, grain, audience, cadence, decision supported
 3. /explore   (LLM + Python) KPI resolution to canonical -> candidate assets (embedding + KPI-set Jaccard + scope match)
                              -> evidence per candidate: usage, owner status, endorsement, refresh, lineage, signals, DQ
 4. Decision   (Python score, LLM explains)  REUSE | EXTEND | CONSOLIDATE | MIGRATE | RETIRE | NEW_BUILD | NOT_FEASIBLE
                              every line cites rule IDs (RULE-001..008) and record IDs (AST-, SM-, KPI-, SIG-)
 5. Human gate (UI)           data steward / BI owner approves or rejects; audit log
 6. /to-spec   (LLM)          only for NEW_BUILD / EXTEND: DashboardSpec on canonical KPIs + certified model, <= 1 page, few KPIs
 7. render     (Python)       deterministic preview + .PBIP skeleton (text files, git-able), owner + certification baked in
```
NOT_FEASIBLE = catalog lacks the data -> loop back to grill-me (his feasibility loop).
Side view for IT: **estate hygiene queue** (orphaned owners incl. the 65 inactive-owner assets, certified-but-stale,
duplicate clusters, Tableau backlog re-triage under RULE-006). Same evidence engine, no prompt needed.

## Decision logic (deterministic first, LLM explains)
- REUSE: candidate covers >= ~80% of requested canonical metrics, same product/market scope, certified/promoted, healthy refresh, active owner.
- EXTEND: good candidate missing 1-2 metrics that exist on its semantic model.
- CONSOLIDATE: >= 2 near-duplicates (same scope, KPI-set Jaccard >= 0.6, Copy/v2/Final/Legacy names).
- MIGRATE: Tableau asset with real usage and no PBI twin; target = certified shared model.
- RETIRE: low usage (< 1,000 views / 10 months) AND (duplicate OR no active owner); never auto, always human-approved.
- NEW_BUILD: no candidate above threshold and catalog supports the metrics.
- Use usage numbers, NOT lifecycle_status / estimated_audience / backlog path (all shown to be noise, see 03).
Thresholds are our assumptions: state them in README and make them config.

## Why this scores (map to criteria)
| Criterion | How we hit it |
| --- | --- |
| 30% fit & value | Literally implements START_HERE MVP + Panu's 4 work packages; headline metric "dashboards NOT built" |
| 25% governance | canonical KPIs, owner required, lineage impact, HITL approval, audit trail, rule-ID citations, .PBIP in git |
| 20% tech & AI | LLM where judgement is needed (interview, KPI mapping, explanation, spec); Python where it must be exact (scoring, render) |
| 15% usability business + IT | two views: requester chat + IT queue; plain-language questions, no spec jargon |
| 10% scale & demo | metadata-only design, swap Excel for Power BI/Fabric scanner APIs; small eval on hold-out |

## Demo story (2 min video, real data-pack records)
1. Request REQ-0001 "global Nubeqa dashboard..." whose metadata says Beyonttra/EMEA -> agent asks one clarifying question (trap #1).
2. Explore finds existing assets, shows 3 near-duplicate Nubeqa reports, non-canonical KPI variants -> **CONSOLIDATE/REUSE**, evidence cards with IDs.
3. A Tableau replacement request -> agent says don't migrate 1:1 (RULE-006), low usage + inactive owner -> retire 2, migrate 1.
4. One genuine gap -> spec -> preview -> .PBIP folder. Steward approves; audit log entry.
5. Closing number: "Of 150 requests, X% resolved without a new dashboard" (compute it, never invent).

## Fit with our existing scaffold (~/SinceAI2026, see project doc workspace-setup.md)
Scaffold = scored queue with evidence + approve/reject + audit trail + eval. Maps cleanly:
`LABELS` = the 7 decisions; `Item` -> `AnalyticsRequest`; demo/inputs.jsonl = 5-10 Business_Requests (one wow = REQ-0001,
one messy, one edge = NOT_FEASIBLE); eval/holdout.jsonl = 30-50 hand-labelled requests across all 10 templates, label BEFORE tuning.

## Strongest objection to this plan
The jury may want to *see a dashboard get built* (slide ends in .PBIP). If our demo is all "don't build", it can feel like
a filter, not a factory. Mitigation: guarantee one NEW_BUILD path renders a real preview + .PBIP skeleton end to end.
Second risk: .PBIP generation is fiddly; fallback is spec JSON + HTML preview, labelled as such.

## Questions for Panu at Saturday Q&A (09:00, Joki), ranked
1. Governance gate vs build factory: which does he weight more? Is our "reuse-first, build only gaps" framing what he wants?
2. Is a real .PBIP expected, or is spec + rendered preview enough for the prototype?
3. Approver persona for HITL: data steward, BI platform owner, or KPI owner?
4. OK to stay in the commercial-pharma data pack, or does he want a manufacturing/shop-floor example too?
5. Business_Requests product_context contradicts the text in 65/75 cases: intentional noise?

## Team split suggestion (from memory of roles; adjust)
- Gajus: product, pitch, decision rules, README, video.
- Martynas (data analyst): data loader, evidence engine, signals re-derivation, hold-out labelling.
- Margiris (quant econ): scoring/thresholds, eval metrics, duplicate clustering.
- Donatas: grill-me question bank + UX copy for non-technical users, demo walkthrough, QA.

## Assumptions that would change this plan
- If Panu says he wants the factory more than governance (medium-low likelihood given the written scoring), shift weight to spec/render.
- If .PBIP is mandatory, render becomes a top-3 risk; prototype it Saturday morning first.
