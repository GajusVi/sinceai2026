# Martynas: Saturday from 08:00 (plan v2, the Dashboard Factory)

Tell your Claude Code: "Do docs/tasks/martynas.md. Read CLAUDE.md and docs/BUILD_PLAN.md sections 0-6 first."

**What changed while you slept (read this first, 5 min):** at 03:10 Gajus made the governed, rendered dashboard + .PBIP the end
product of every verdict (BUILD_PLAN v2). To show Panu a working draft at 09:00, Gajus and Margiris drafted some of your files tonight:
- `steward/models.py`: additive fields only (e.g. `StewardResult.spec`; Gajus, N3)
- `steward/spec.py` v2 (contract C5, additive) + fixture `tests/bi_steward/fixtures/spec_req0001.json` (Gajus, N1)
- `catalog/bayer/measures.json` + new `steward/semantic.py` (the semantic layer + feasibility; Gajus, N2)
- new `steward/pbip.py`, TMDL half only (Margiris, N7)
They are yours again from 08:00. Read NOTES.md (night handover lines) and `git log --since=03:00` first.
Your files: steward/models.py, spec.py, catalog.py, semantic.py, pbip.py, catalog/, data/, templates/pbip/.

## M0 (08:00, 2 min) take your files back
In OWNERS, change the NIGHT lines for steward/models.py, steward/spec.py, steward/semantic.py, steward/pbip.py and catalog/bayer/measures.json back to
`martynas` (delete the NIGHT text). Commit "OWNERS: Martynas takes back night files".

## M1 (08:00-09:30, P0) review the night drafts: contract + bindings
- spec.py: matches BUILD_PLAN section 3 (C5)? All new fields defaulted? Anything you would name differently, change it now, before
  others build more on it (tell Gajus, Margiris and Donatas with `say all`).
- measures.json: check each of the 18 bindings against the xlsx (BUILD_PLAN section 4: 12 bound, 6 gaps). Units right (KPI-042 is EUR
  in KPI_Catalog; data has EUR difference and %)? DAX expressions plausible? Trap 14 handling present?
- semantic.py: feasibility returns the expected results (REQ-0001 = 3 buildable; template 2 = 1 buildable + 2 gaps); tests cover it.
Done when: NOTES.md line "contract + bindings reviewed: <changes>" by 09:30.

## M3 (09:30-11:00, P0) Power BI Desktop templates
Install Power BI Desktop (free, Microsoft Store). Options → Preview features: enable Power BI Project (.pbip) save, TMDL, PBIR.
Save into `templates/pbip/`: (a) an empty project; (b) a project on a small CSV with exactly one card, one line chart, one clustered bar
and one table. These files are the ground truth for the format: never hand-write PBIR from memory. Commit, with the Desktop version in a README line.

## M4 (11:00-18:00, P0) finish `steward/pbip.py`
Keep Margiris's TMDL half (fix it against your saved template). Add the PBIR report half: one page per spec page, visuals copied from
the template of the same type with field references replaced. Open the zip in Desktop; screenshot to `submission/pbip_open.png`.
**18:00 fallback (BUILD_PLAN section 7):** if it does not open, ship the TMDL model + spec JSON, labelled "not verified in Desktop".
Write which in NOTES.md either way. Post `done` to all.

## M5 (after M4, P1, with Margiris) 20 hold-out rows with expected verdict + best asset
`data/holdout/`: 2 per request template, labelled before any threshold tuning.
