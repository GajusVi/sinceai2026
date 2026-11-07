# Donatas: Saturday from 08:00 (plan v2, the Dashboard Factory)

Tell your Claude Code: "Do docs/tasks/donatas.md. Read CLAUDE.md and docs/BUILD_PLAN.md sections 0-6 first."

**What changed while you slept (read this first, 5 min):** at 03:10 Gajus made the governed, rendered dashboard + .PBIP the end
product of every verdict (BUILD_PLAN v2). To show Panu a working draft at 09:00, Gajus drafted tonight:
- new `steward/render.py` (spec → KPI cards, trend, breakdown, exceptions, gap cards, governance footer; Plotly)
- a dashboard panel in `frontend/steward_app.py` under the decision (filters, lint panel, approve writes the spec hash to the journal,
  spec JSON download). Your existing tabs were kept.
Both are yours again from 08:00. Read NOTES.md (night handover lines) and `git log --since=03:00` first.
You now own what the jury sees: the dashboard is the centre of the screen. **Saturday is for quality and design.**
Your files: frontend/, demo/, submission/, steward/render.py.

## D0 (08:00, 2 min) take your files back
In OWNERS, change the NIGHT lines for frontend/steward_app.py and steward/render.py back to `donatas` (delete the NIGHT text; the
frontend/steward_app.py line can go, frontend/ covers it). Commit "OWNERS: Donatas takes back night files".

## D1 (08:00-09:00) review the draft, then Panu Q&A with Gajus at 09:00 (Joki)
Run `make bayer`, ask the REQ-0001 text, approve. Note everything that looks rough. Gajus shows the draft to Panu at 09:00; write
down what Panu says about the screen.

## A2/A3 (09:00-11:00, P0) evidence + KPI card on the real engine
Evidence cards from `decision.evidence` (rule id badge, record ids, severity colour); drop FAKE_EVIDENCE when real evidence exists.
KPI disambiguation card: canonical vs variants (status, owner), canonical preselected, choosing a variant needs a reason.

## R2 (11:00-15:00, P0) dashboard polish and design
- Layout: the dashboard reads in 10 s by an outsider. Headline cards on top, trend and breakdown side by side, exceptions below.
- Filters (product, market/region, month range) applied to every visual.
- EXTEND: elements added by `spec.changes` get a "new" badge and a highlight; CONSOLIDATE shows the retire list.
- Lint panel: pass / warn / block per rule with its message; any block disables approve and says why.
- Gap cards stay grey with the reason, never a number. Footer on every page.
- Design: write a `DESIGN.md` at the repo root first (format: docs/vendor/design-md/spec.md, Google's DESIGN.md spec, examples next to it;
  check it with `npx @google/design.md lint DESIGN.md` if Node is installed), then apply it: our palette, no default Streamlit look where
  it hurts, consistent number formats (EUR m, %, weeks). 70+ real-brand examples: Gajus's Hackathon Resources/design-repos/awesome-design-md.
Test: the fixture `tests/bi_steward/fixtures/spec_req0001.json` renders; a gap measure renders as a gap card.

## R3 (15:00-21:00, P1)
- "Dashboards" tab: every approved spec rendered as a gallery card (what the factory produced, and how many requests needed nothing new).
- Estate door: a health-tab item (consolidate / migrate / retire) → "Build the merged dashboard" → same W5-W9 path.
- Orphan rescue tab: after successor acceptance, render the repaired version.
- .PBIP download (Martynas's `export_pbip`) next to the spec JSON.
- Demo cache: `make warm` on **Gemini** (not Aitta: the cache key ignores the model) for the 5 demo beats (BUILD_PLAN section 8).

## A9 (Sun 06:00, P0) video ≈2 min
Must show the rendered dashboard, the lint gate and the .PBIP download (or the labelled fallback). English narration, captions,
screen recording, label anything mocked, no invented numbers.

Post `done` to all after A2/A3 and R2 (commit ids, how to use it, what is still missing).
