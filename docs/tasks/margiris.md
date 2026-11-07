# Margiris: NIGHT SHIFT (Sat 03:30 → 08:30), then Saturday

Tell your Claude Code: "Do the NIGHT SHIFT in docs/tasks/margiris.md. Read CLAUDE.md and docs/BUILD_PLAN.md sections 0-6 first."
Goal: Gajus builds the end-to-end draft (Track A); you add the parts that say "no" and the export (Track B) so the 09:00 draft
for Panu is complete (BUILD_PLAN 6.1). **Confirm on the board by 03:45** (`tools/coord.py say gajus "on it" --kind fyi`), otherwise
Gajus takes N5 later and N6/N7 move to the morning. You never touch Gajus's night files; he never touches yours.
Tonight you are also the NIGHT owner of steward/pbip.py (OWNERS). Push after each N-task and `say all --kind done`.

## N5 (03:45-06:00) `steward/lint.py`
`lint(spec, catalog) -> list[LintResult]`, `can_approve(spec) -> bool` (no block). Rules exactly as BUILD_PLAN 5.2 (RULE-001..008,
FOCUS, DATA). Start from the C5 contract in BUILD_PLAN section 3 (field names are final); switch to Gajus's fixture
`tests/bi_steward/fixtures/spec_req0001.json` when he pushes it (~04:00). One pass and one fail test per rule (edit a copy of the
fixture). RULE-001 for CREATE: any compatible asset with canonical-KPI Jaccard ≥ 0.6 on the same product + market scope blocks it.
Gajus's `Steward.build` calls `lint` automatically once it imports.

## N6 (06:00-07:30) L5: CONSOLIDATE + NOT_FEASIBLE
NOT_FEASIBLE from `steward.semantic.feasibility(intent)` (Gajus pushes ~05:00): no requested measure buildable → NOT_FEASIBLE, the
gaps as Evidence (KPI id, gap_reason) and the nearest buildable alternative. Partly feasible stays in the normal verdict path
(the spec keeps the gaps). CONSOLIDATE: ≥ 2 compatible candidates, same product scope, canonical-KPI Jaccard ≥ 0.6 → keeper = most
trusted, the others listed with record ids. Goldens: batch yield → NOT_FEASIBLE (remove its known_gap), template 2 shows its gaps.

## N7 (07:30-08:00) `steward/pbip.py`, rough TMDL half
`export_pbip(spec, frames, out_dir) -> Path` (zip): `<name>.pbip`, `<name>.SemanticModel/definition.pbism` and
`definition/` with model.tmdl, tables/*.tmdl (columns + the spec's measures with the DAX from measures.json; data as CSV in the project),
relationships.tmdl; `<name>.Report/definition.pbir` pointing at the model byPath. Layout per Microsoft's PBIP docs
(learn.microsoft.com/power-bi/developer/projects/projects-dataset); do not invent the report visuals, Martynas adds the PBIR report half
from Desktop templates on Saturday. Label the zip README "draft, not opened in Power BI Desktop yet". Tell Gajus the function name;
Saturday Donatas wires the download.

## 08:15 handover
`tools/coord.py status`, 3 lines in NOTES.md (done / rough / missing). Then sleep; Saturday tasks below start when you are back.

---
Tell your Claude Code: "Do docs/tasks/margiris.md. Read CLAUDE.md and docs/BUILD_PLAN.md sections 0-6 first."
## Saturday (after the night shift and some sleep): hardening
- **L5 (P0)** remaining flags MIGRATE / RETIRE / REASSIGN_OWNER / FIX_REFRESH with evidence ids (RULE-008); goldens green.
- **L11 (P0)** harden lint: RULE-001 on the real search + coverage, RULE-004 with lineage impact (L7), edge cases from Panu's feedback.
- **L8 (P0)** `eval/eval_steward.py` → eval/results.json: verdict accuracy, **false-REUSE rate** (headline), intent F1, confusion matrix,
  misses, **spec lint pass rate**, **share of requests resolved without a new dashboard**. v1 at S3 (12:00), v2 at freeze. Only you commit results.json.
- **L6 + L7 (P1)** RETIRE per BUILD_PLAN 2.2; lineage impact for CONSOLIDATE / RETIRE. Numbers checked against docs/challenge/03_DATA_PACK.md.
- Still open: the backend LLM fallback ask (aitta → gemini → rules), coord ask 1107-030434. Cut L9 fastembed.
