# Audit: Martynas's Claude (Sat 7 Nov, phase 1, blind)

Deep stretch: **7 data + semantics, 8 spec contract, 12 PBIP, 13 estate health.** The other nodes are short, from tracing real requests; where I only read code or did not check, I say so.
Everything below was run on `main` at 18:35 (STEWARD_CATALOG=datapack, STEWARD_USE_LLM=off, so 0 LLM calls) unless a line says "large pack" (`make pack-large`, 5,000 assets).
Scratch scripts live outside the repo; the numbers can be re-run with the commands named in each section.

## Traces (what I ran)
| Request | ask | Verdict | build (builder / manager / worker) |
|---|---|---|---|
| "How are we doing in LATAM this quarter?" | 0.0 s | CLARIFY, unmapped = `doing` | no spec |
| "Is supply safe for Plant-B?" | 0.0 s | CLARIFY, unmapped = `supply, safe, Plant` | no spec |
| "Xarelto net sales in Germany" | 0.2 s | REUSE AST-0191, filters product=Xarelto market=DE | card+line for all three roles |
| REQ-0001 Nubeqa global | 0.0 s | EXTEND AST-0335, filters product=Nubeqa | 7 / 6 / 4 visuals, 0.1 s each, lint all pass, PBIP 24-27 files, ~125 KB |
| "Kerendia batch yield and net sales for Mars" | 0.0 s | CLARIFY, unmapped = `batch, yield, Mars` | no spec |

Rules-only mode (`make demo`) CLARIFYs two of the three "real" floor questions. That is where the LLM path matters; I did not call it (live key rate-limited me with a 429 earlier today).

---

## 7. Data and semantics (deep)
**In / out.** Data pack xlsx (24 sheets) + `catalog/bayer/measures.json` in; `semantic.load_frames()` star schema (9 frames), `measure()`, `feasibility()`, `compute()`, `scoped_frames()`, `profile()`, `check_visual()` out.

**How it works now.** `semantic.py:43` loads frames, `:140` feasibility on KPI ids, `compute` (`:358`) is the Python reference, `measures.json` carries the DAX for the PBIP. 18 canonical KPIs: 12 bound, 6 gaps (KPI-023/034/037/039/046/049). Trap 14 (110 zero-sales rows) and the forecast_like-as-actual flip are reported as DQ notes on the card.

**Assumptions ("because it worked").**
1. Averages of percentage columns are unweighted row means (KPI-016/020/027).
2. Time is a month grid; `month_from`/`month_to` exist as filters (`semantic.py` `_months`) but nothing produces them.
3. `measures.json`, `catalog/bayer/metrics.json` and the xlsx `KPI_Catalog` are three sources for one KPI definition.
4. Python `compute` is the truth and DAX is "equivalent".

**Attacks (repro + result).**
- **A1. A time constraint is silently dropped** (Donatas found the same, pushed first: his idea, my evidence). "this quarter" -> `quarter` is in `STOPWORDS` (`config.py:99`), `Intent.grain` has `"quarter"` (`intent.py:31`) but no code reads it, and `grep month_from steward/ frontend/` finds it only in `semantic.py`. "LATAM this quarter" would show all 10 months with no note. This breaks the no-silent-drops rule (L3) in the exact place a floor user speaks (quarter, last 3 months, YTD).
- **A2. DAX is verified in Desktop for 4 of 12 measures.** The REQ-0001 cards (KPI-001/004/027/042) match the app. KPI-006/010/014/016/020/031/051/054 have never been opened in Desktop; a DAX typo shows as a broken visual on stage. I built a check export: `C:\SinceAI\pbip_all_measures\unzipped\All_governed_measures_check.pbip` (12 cards, Nubeqa). Expected values: 001 3,347.72 · 004 -0.1415 · 006 86.3 · 010 -0.015 · 014 10,095,502 · 016 5.8394 · 020 82.6693 · 027 66.3757 · 031 21.4286 · 042 -50.81 · 051 71.3434 · 054 12.5. Needs one person with Desktop, ~5 minutes.
- **A3. Unweighted averages.** Nubeqa KPI-027: simple mean 66.38, sales-weighted 65.44 (-0.93); OTIF 82.67 vs 82.62; inventory weeks 5.84 vs 5.77. On this pack the difference is under 1 point, so keep it, but a Bayer reader would ask. It belongs in the README as an assumption.
- **A4. Startup is dominated by reading Excel twice.** Large pack: `Steward()` 46.6 s; the profile shows 2 `pandas.read_excel` calls = ~90 s of 105 s profiled (openpyxl, 587k rows), once for the catalog (`datapack.py:218`) and once for the frames. Original pack: 2.9 s. Gajus's note says "startup ~40 s"; this is why.
- **A5. Scale is fine downstream.** Large pack: `compute` 0.01 s, `profile(4)` 0.17 s, `pbip.build_files` 0.1 s, zip 42 KB (REQ-0001 embeds 4 tables: dim_market, dim_month, dim_product, fact_pmm; fact_usage has 262k rows on the large pack and only ships when a usage KPI is in the spec).
- **A6. Gaps are well handled; they are also a dead end.** A gap card says "no governed source data" and stops. All six gap KPIs have an **active named owner** in `KPI_Catalog` (e.g. KPI-034 -> OWN-028 Launch Excellence Lead) and 4 of 6 are high criticality.

**Optimise.**
- Cache the parsed pack once (parquet/pickle next to the xlsx, keyed by mtime) and have `datapack` and `semantic` share it: large startup 46 s -> a few seconds, one read instead of two. **S, 1-2 h.**
- Add a Python-vs-DAX conformance table in `measures.json` (expected value per KPI on the original pack) so a Desktop check is a diff, not an eyeball. **S, 1 h.**
- Drift test: `measures.json` vs xlsx `KPI_Catalog` names/units (only partial today). **S.**

**0 to 1.** *Turn a gap into a governed data request.* A gap card gets a button: "Ask <owner, role> for the source data of KPI-034". It is journaled, shows up in the owner's queue, and the KPI stays NOT_FEASIBLE until a source is attached. No other team will connect "this KPI has no data" to "this person is accountable for it".

**Effort / impact.** Time as first-class (A1) is **M, ~3 h**, touches Intent, parser, specbuild, semantic, render, PBIP (contract change: `Intent.period`), and fixes the most visible floor-user failure. Cache **S**. Gap request **M, ~3 h**, mostly UI + journal.

**Verdict.** Keep the semantic core. **Improve**: time, DAX conformance, startup. Replace nothing.

---

## 8. Spec contract (deep)
**In / out.** Decision + Intent + feasibility in; `DashboardSpec` (v2 + `Visual.step/question`) out; consumed by lint, render, journal, PBIP.

**How it works now.** `spec.py` (90 lines): `Measure`, `Visual`, `Page`, `SpecChange`, `LintResult`, `DashboardSpec`. `specbuild.spec_hash` hashes everything except `lint` and `provenance` (`specbuild.py:42`).

**Assumptions.** One spec per (request, verdict); the layout is part of the spec; the spec hash is "what the human approves".

**Attacks.**
- **S1. Dead and duplicated fields.** Outside `spec.py`: `rationale` 0 readers, `cadence` 2, `data_label` 2, `grain` 2, `relationships` 2, `entities` 3. `entities/columns/relationships/grain` are the model schema and are consumed by `pbip.py` and are also derivable from `semantic.star_schema()`. They make the spec look like a data model when it is a dashboard decision.
- **S2. One request, three specs.** REQ-0001 gives hashes `b073a8c5…` (builder, 7 visuals), `5b7176ab…` (manager, 6), `e9c78f84…` (worker, 4; hidden: "Market Access Coverage"). The journal stores one hash. The approved artifact is the builder's; what the worker is shown is a different hash that nobody approved. `layout_hidden` is in `provenance`, which is excluded from the hash.
- **S3. `provenance` is an untyped `dict[str,str]`.** It carries layout_source, role, fallback, reason, hash: queried by string keys in 16 places.
- **S4. Hash stability holds** for rules mode (same input -> same hash, checked). With the LLM layout, two runs can produce two hashes for the same request (a new "approval" each time) unless the disk cache is used.

**Optimise.** Split the spec into *decision* (verdict, KPIs, scope, measures, changes: hashed and approved) and *presentation* (layout per role: derived, hashed separately, never approved separately). Type `provenance`. Drop `rationale`, move schema out. **M, 3-4 h** because lint, render, journal and tests read it.

**0 to 1.** *The approved object is the decision, the dashboard is a view of it.* A worker sees a role view of one approved decision; the journal proves which decision and which view. This makes "personalised but governed" literally true and is a one-sentence pitch line.

**Verdict.** **Improve** (separate decision from presentation); keep the field set otherwise.

---

## 12. Power BI export (deep)
**In / out.** Spec + frames in; `.pbip.zip` out (TMDL model with embedded data + PBIR report). Verified in Desktop 2.159 on REQ-0001 (4 cards, line with forecast, bar, table).

**How it works now.** `pbip.py:~460 lines`: data embedded as deflated base64 in Power Query, visuals copied from Desktop-saved templates, layout follows `Visual.step`, scope trimmed by `semantic.scoped_frames`.

**Assumptions.** The export is a static snapshot; only 4 visual types; layout is code geometry; the spec is the role's spec.

**Attacks.**
- **P1. Role parity holds by construction.** Builder spec 7 visuals -> 7 exported; worker spec 4 -> 4 exported. The export matches the page the viewer sees.
- **P2. Title/subtitle/filters/threshold table are missing.** The Desktop ground truth for title + subtitle is now saved (card `visualContainerObjects.title/subTitle`, literal `'text'`), but I was told to stop (PBIP task retracted at 18:23), and my commit of it was not made. It sits uncommitted in `templates/pbip/one_of_each/`. Page filter format is still unverified (Desktop only changed `outspacePane` in report.json).
- **P3. Export is not a connection.** The data is a frozen copy; "Refresh" re-reads the embedded table, not the governed source. To a Bayer BI person that is "a screenshot with measures", honest but limited.
- **P4. Only 4 of 12 measures verified in Desktop** (see 7/A2).
- **P5. A builder can edit the PBIP in Desktop and nobody knows.** Change the Net Sales DAX, save, share: a variant KPI is born outside the catalog (the exact thing RULE-002 exists to stop).

**Optimise.** Verify all 12 measures (export ready); add title/subtitle/filter from the saved ground truth; apply the table threshold; stamp the spec hash inside the model (a TMDL annotation) so an exported file can be traced to its approval. **S-M, 3 h.**

**0 to 1.** *PBIP round trip with drift detection.* (Related to Donatas's "the approval is a contract that re-checks itself", pushed first: his replays the **journal spec** on today's catalog; mine reads the **.pbip file in the wild** back and diffs its measures against the governed ones. Different input, same governance loop.) Read a `.pbip` back (TMDL measures), compare each measure's DAX with the governed expression in `measures.json`, and flag "KPI drift: Net Sales differs from KPI-001" before it re-enters the catalog; show the spec hash it came from. The export stops being a one-way file and becomes a governed artifact that can be audited. **M-L, 4-6 h**, TMDL is plain text so the reader is small.

**Effort / impact.** Judges: "Prompt in, .PBIP out" is Panu's framework; the drift check answers "what happens after we hand it over?".

**Verdict.** **Improve**, then add the round trip if time allows.

---

## 13. Estate health (deep)
**In / out.** Catalog + as-of date in; `CatalogHealth` (duplicates, stale, no_owner, retire, human_review, funnel, ownership) out, plus per-request lifecycle flags.

**How it works now.** `health.py` -> `decision/lifecycle.estate()` implements BUILD_PLAN 2.2. Original pack: 0.3 s. Output: 360 assets, 50 certified, **125 duplicate pairs**, **257 stale**, 86 "no owner" (65 inactive + 21 none), **21 RETIRE**, 0 human review; funnel 360 -> 354 old enough -> 74 low use -> 62 quiet -> 21 reason -> 21 not critical. Ownership tiers 23 / 21 / 21 / 21 (matches the plan). 69 failed refreshes, **16 certified assets sit on a failed refresh**.

**Attacks.**
- **H1. "Stale" does not discriminate.** `STALE_AFTER_DAYS=90`; median asset age is 166 days; 257 of 360 (71%) are stale. A list that is 71% of the estate is not a list.
- **H2. The critical-KPI guard never fires.** `not_critical` keeps all 21 retire candidates; `human_review` is 0. The rule is implemented and tested but has no effect on this pack (fine, but it should not be pitched as doing work).
- **H3. Quadratic cost.** Large pack: `catalog_health` 22-34 s. `_more_trusted_duplicate` is called for 5,000 assets and re-scans `active_artifacts()` each time (3,744 calls, 7 s in the list comprehension, 25 s cumulative). Fixable by grouping once by metric set.
- **H4. The best finding is not surfaced as a finding.** 16 certified assets are on failed refresh (`certified_on_failed_refresh`, `health.py:134`); the trust score gives a certified asset 0.40 even if its data is not refreshing. This is a governance contradiction worth a headline.
- **H5. No per-builder view.** Panu point 6 asks for "my assets: life cycle, failed refresh, owner gone, usage trend". `Estate` is estate-wide only.

**Optimise.** Precompute duplicate groups (22 s -> ~1 s). Replace "stale" with "stale relative to its peers / to usage". Join `Estate` to `Owners` for a per-owner list. **S-M, 2-3 h.**

**0 to 1.** *"Certified but broken" as the estate's headline number.* The data pack says Certified, our trace says refresh failed 16 times; a per-owner "your 4 assets need attention" view is Panu's builder persona and the easiest demo of life cycle.

**Verdict.** **Improve.**

---

## Other nodes (short; from traces, deeper reading only where stated)
- **0 Roles/hierarchy.** `Steward.build(result, None, user)` does **not** scope data to the user's plant: Worker21's spec for Nubeqa has `filters={'product': 'Nubeqa'}` only. Plant scoping happens in `worker.py` (`sites=[user.plant]`), so it depends on the caller. Move scope into `build()` by role. **Improve (S).**
- **1 Intake.** Not audited beyond the trace.
- **2 Understanding.** Rules mode misses the 2 floor questions (`Plant` and `doing` unmapped; `quarter` is a stopword -> A1). LLM path not exercised (rate-limited). **Improve**: tell the user what was dropped, never only CLARIFY.
- **3 Grill-me.** Not audited (646 lines, not read).
- **4 Search / 5 Decision.** Margiris's H-01 miss is visible in my trace: REQ-0001 returns EXTEND on AST-0335, which carries 1 of the 3 requested KPIs (33%, plan says >= 50%). Not my stretch; flagged for her.
- **6 Explanation.** Not audited.
- **8 Layout.** Roles are consistent now (worker 4, manager 6, builder 7), gaps recorded when cut. See Spec/S2 for the hash issue.
- **9 Lint.** All three REQ-0001 role specs pass every rule; I did not test whether lint ever blocks.
- **10 Render, 11 Governance.** Not audited.
- **14 Proof.** The 25-row hold-out is mine and unmodified; `eval/results.json` v1 is Margiris's.
- **15 LLM infrastructure.** Call sites: query parse, interview (per turn), explain, investigate, takeaway, layout, worker pick, departments, embeddings. A builder request can chain 5+ sequential calls; a live 429 hit me today and the template fallback worked. `make warm-layout` exists for the layout cache.

## End to end
- **Builder:** works; fast (all stages under 1 s without the LLM); the PBIP matches the page.
- **Manager:** gets 6 visuals; data scope depends on the caller, not on `build()`.
- **Worker:** 4 visuals, honest about hidden items; fast path is code, not the build chain.
- **Breaks:** time words (A1), vague floor questions in rules mode (2/3 CLARIFY), large-pack startup (A4), the certified-but-broken contradiction is invisible (H4).
- **LLM calls per request:** 0 with LLM off; up to 5+ with it on (not measured live).

## Top 3 changes (mine, ranked)
1. **Verify and pin every governed measure**: open `C:\SinceAI\pbip_all_measures` in Desktop (5 min), add the expected-value table, drift test vs xlsx. **S, ~2 h.** Without this, 8 of 12 KPIs are unproven on stage. (Mine alone.)
2. **Make the estate story and the speed real**: cache the pack (46 s -> seconds), fix the quadratic duplicate check (22 s -> ~1 s), headline "16 certified assets on a failed refresh" and group problems by root cause (see "5 more optimisations", 2). **S-M, ~4 h.**
3. **Period in the exported model** (I dropped my own "time as a first-class part of the request": **Donatas pushed it first**, `docs/audit/donatas.md` TL;DR 2 and top 1, with a better number: LATAM "this quarter" shows EUR 2,431 M, the last 3 months are EUR 692 M). His is the app side. My part is the model side: `dim_month` gets quarter / year / YTD columns, in `semantic` and in the TMDL, so a period is a slicer in Desktop and a DAX filter, and the app's `month_from/month_to` and the exported model agree. My independent evidence for the same bug: `quarter` is a stopword (`config.py:99`), `Intent.grain` has `"quarter"` (`intent.py:31`) and nothing consumes it. **S, ~1-2 h**, after Donatas's `Intent.period` contract.

## One bold idea for the whole chain
**The chain is a governed round trip, not a one-way generator.** Question -> verdict -> *decision* (approved once, hashed) -> role views -> `.pbip` carrying the decision hash -> **re-import any `.pbip` and diff it against the governed measures and the approved decision**. Other teams generate a dashboard; ours can also tell you, a month later, that the file on your laptop no longer means what the catalog says, who owns the fix, and which KPI has no data and whom to ask. That is the "governed analytics" in the challenge title, shown as a loop instead of a claim.

## Housekeeping found
- `templates/pbip/one_of_each/.../visual.json` + README title ground truth: **uncommitted**, my commit was interrupted. Needs a go-ahead (templates/pbip is mine).
- `stash@{0}` ("unknown edits, check Sat") and `stash@{1}` (unlabelled) still unchecked; `submission/pbip_open.png` still untracked (Donatas).

---

# Added for Gajus's 18:50 rule: 5 more optimisations + 4 more bold ideas
Read first: `docs/audit/gajus.md` (18:43, plus his follow-up O1-O6 / B1-B5) and `docs/audit/donatas.md` (c694751), both on main before I pushed. His ideas I do **not** repeat: policy-as-data, "your 3 numbers today", one understanding pipeline with ids, decide over the full coverage index, value-of-information interview, one explanation call, the ruling as a document, data-first deterministic layout, per-step receipts, intent receipt. Where mine builds on one of his, I say so.

## 5 more optimisations
1. **A calendar in the model, not just in the app.** `dim_month` has one column (`month`). Add `quarter`, `year`, `month_index`, `is_ytd`, `is_last_3_months` to the `dim_month` frame and the TMDL, and write the matching DAX (`CALCULATE(..., dim_month[is_last_3_months])`). Then "this quarter" is one slicer in Desktop, the Python reference filters the same rows, and `month_from/month_to` becomes derived instead of hand-typed. This is the model side of Donatas's period fix (his idea, pushed first; I add what he does not cover). **S, 1-2 h.** *(Replaces my earlier "governed targets" idea: Donatas's "tone from KPI direction" already puts `better_is` in `measures.json`. The open part, target values per KPI, is a contract question I note for phase 2: only 3 of 12 KPIs have any threshold, `specbuild.py:32`.)*
2. **Group estate problems by root cause.** 69 assets sit on failed refresh but only **14 semantic models** are failing (SM-060 feeds 9 assets, SM-047 feeds 8, SM-043 feeds 6; 16 of the 69 are certified). 65 assets sit with **13 inactive owners** (OWN-059 holds 10, OWN-029 and OWN-044 hold 9 each). `Estate` counts assets; it should count *actions* and the assets each one heals. "14 model fixes + 13 reassignments" is a plan a builder can finish; "134 problem assets" is not. **S, 1-2 h** on top of `lifecycle.estate`.
3. **Derive `feasible` from the data, not from a hand-set flag.** `measures.json` carries `feasible: true/false` per KPI by hand. If a column/sheet that a measure needs exists, the KPI is buildable; if not, it is a gap with the missing column named as the `gap_reason`. Then the six gaps close by themselves on a pack that has the data, and the large pack or any other estate needs no code change. **S, 1-2 h.**
4. **Load the lint rules' wording from the pack's `Governance_Rules` sheet.** The sheet has RULE-001..008 (name, description, priority); no app code reads it (only `tools/make_large_pack.py` copies it), `lint.py` hard-codes them. Lint results then quote Bayer's own rule text, and a changed rule sheet changes the cards. Adjacent to Gajus's policy-as-data (roles); this is the other half (rules). **S, 1 h.**
5. **Put the expected values in the PBIP README / a `check.json`.** Today I compared four Desktop cards with the app by eye. The export knows the Python-reference value for every measure it ships; write them into the zip (`check.json` + a README table) so opening the file is a self-test. **S, 1 h.**

## 4 more bold ideas
1. **Ownership continuity as part of the pipeline (Panu point 9, the opening fragment).** Donatas pushed an owner pick-list from the Owners sheet (his Governance finding 5); that is the floor. What I add is the chain and the reason: "If the owner leaves, who owns the asset and why does it exist." Make an owner chain (person -> role -> named successor) and a one-sentence *why this exists* (the requester + `decision_supported`) mandatory fields of every approved spec. Approval is impossible with an inactive owner. A leaving owner generates a handover pack ordered by blast radius (OWN-059: 10 assets). Evidence the problem is real: 13 of 60 owners are inactive and hold 65 of 360 assets. Nobody has the lifecycle *and* the reason in the same record.
2. **An "About & governance" page inside every PBIP.** Page 2 of the exported report lists, from the spec: governed KPI ids and DAX, the gaps and who owns them, approver and requester, owner and refresh status, the spec hash, the data label, DQ notes. Built from the table visual and an embedded table (both already proven in Desktop), no new visual type. A judge or a Bayer reviewer who opens the file *without* our app still sees the governance. The file proves itself. (Builds on the spec-hash stamp in section 12.) **M, 3 h.**
3. **"Show your work" on every number.** Click a figure and see: the governed KPI, the DAX, the source column, how many rows fed it, which rows were left out and why (e.g. 110 zero-sales rows, trap 14; 491/489 value_type flips), its owner and status. `compute` already returns the DQ notes as `attrs["dq"]`; the row counts are one `len()` away. Gajus's ruling-as-a-document footnotes *sentences* to record ids; this does it for the *numbers*, which is where a finance reader distrusts a dashboard first. **M, 3 h.**
4. **A transfer-conformance report: "does your estate fit?"** `make conform` takes any pack (`STEWARD_DATAPACK_XLSX`) and prints a pass/fail table before the app starts: sheets and columns present, which of the 18 KPIs bind or become gaps, owners resolve, trap rules detected, asset/usage counts. I ran the 5,000-asset pack today (46 s startup, everything downstream under a second), so scale is proven; what is not proven for a judge is that it works on **another** estate. With optimisation 3 this turns "synthetic demo" into "a tool you can point at your own data". **M, 3-4 h.**

## Notes for phase 2 (so I do not need to re-find them)
- Gajus's data-first layout depends on targets that exist for 3 of 12 KPIs (`specbuild.py:32`); Donatas's `better_is` gives direction but not a target value. Needs a contract decision, not just a field.
- Gajus's node 12 line "Role layouts are not exported": measured the other way, builder spec 7 visuals -> 7 exported, worker spec 4 -> 4 (section 12, P1).
- Gajus's finding F3 (`make demo` loads the 19-asset sample catalog) matches what I saw: without `STEWARD_CATALOG=datapack` my first trace returned CLARIFY on everything.
