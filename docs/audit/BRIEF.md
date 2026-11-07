# Audit brief: attack the whole chain (Sat 7 Nov, Gajus)

The build is paused. Before we write more code, each of the four Claudes audits **the whole BI Steward chain end to end**:
every node, every input and output, every decision we made. This chain (how a question becomes a governed,
personalised, approved dashboard) is our IP. It has to stand out, so this is where 0-to-1 thinking belongs.

**Mindset.** Treat every past decision as "chosen because it worked at the time", not as the best answer. Be sceptical
of every node, prompt, threshold, data structure and handoff. For each, ask:
- Is it needed at all?
- Is it in the right place in the chain?
- What would a 10x better version look like?
- How can it be faster, cheaper, simpler or more accurate?

## The chain (everything counts)

| # | Node | Where to look (start here, follow the code) |
|---|------|---------------------------------------------|
| 0 | Users and hierarchy: roles, plants, departments, permissions, who may see/approve what, request queue to builders | steward/auth.py, steward/worker.py (can_see, other_plant, own_plant_scope), frontend/worker_view.py |
| 1 | Intake: chips, chat box, worker prompts, free-text words to metrics | frontend/steward_app.py, steward/worker.py |
| 2 | Understanding: parsing, Intent, confidence, intent_from_parsed | steward/query_parser.py, steward/intent.py, steward/llm.py, prompts/ |
| 3 | Grill-me interview: which questions, for which role, defaults, when it stops, "Use recommended" | steward/interview.py, prompts/interview.yaml |
| 4 | Search: BM25 + trigram + structure, RRF, linking, KPI index, variants | steward/search/, steward/linking.py |
| 5 | Decision: REUSE / EXTEND / CREATE / CLARIFY / CONSOLIDATE / NOT_FEASIBLE, thresholds, lifecycle flags | steward/decision/, steward/config.py, tests/bi_steward/golden_questions.json |
| 6 | Explanation: investigation trail, explanation, takeaway | steward/investigate.py, steward/takeaway.py, prompts/ |
| 7 | Data and semantics: data pack loader, measures, feasibility, profile, gaps | steward/datapack.py, steward/catalog.py, steward/semantic.py, catalog/bayer/ |
| 8 | Spec and layout: DashboardSpec contract, template, AI layout per role | steward/spec.py, steward/specbuild.py, steward/layout.py, prompts/layout.yaml |
| 9 | Lint: RULE-001..008, FOCUS, DATA, approve gate | steward/lint.py |
| 10 | Render and UI: charts, tiles, novice/expert, design | steward/render.py, frontend/, docs/steward/DESIGN.md |
| 11 | Governance: approve / send back, journal, catalog versions | steward/governance.py, data/steward/ |
| 12 | Power BI export (.PBIP) | steward/pbip.py, templates/pbip/ |
| 13 | Estate health: duplicates, retire funnel, owners, orphan rescue | steward/health.py, steward/decision/lifecycle.py |
| 14 | Proof: eval, golden questions, hold-out, tests | eval/eval_steward.py, tests/bi_steward/ |
| 15 | LLM infrastructure: providers, caching, demo mode, latency, cost, number of calls per request | steward/llm.py, backend/llm.py, demo/cache |

Ground truth for what Bayer wants (read first):
- **docs/challenge/08_PANU_QA.md**: Panu's Q&A takeaways (raw transcript: 08_PANU_QA_transcript.txt). Grill-me
  must exist but stay short; governed KPIs first; tweak before build; one approver; two populations (floor viewers
  find and decide fast, builders maintain the life cycle); judges want the pipeline in a logical sequence with each
  step's input and output and our benefit over other teams.
- docs/challenge/ (brief, Panu's framework, data-pack traps).
- Judge every node against these. Panu's point 8 is the bar: can a judge follow it in a few minutes?

## Who goes deep where (everyone still audits ALL nodes)

| Claude | Deep stretch (most evidence, most ideas) |
|--------|------------------------------------------|
| Gajus | 0 hierarchy, 1 intake, 2 understanding, 3 grill-me, 6 explanation, 8 layout |
| Margiris | 4 search, 5 decision + lifecycle, 9 lint, 14 proof, 15 LLM infrastructure |
| Martynas | 7 data + semantics, 8 spec contract, 12 PBIP, 13 estate health |
| Donatas | 10 render + UI, 11 governance, the end-to-end demo flow per role (worker, manager, builder); this is also the raw material for the pipeline slide (Panu point 8) |

## Rules
- **Read-only.** No code edits. The only files you write are docs/audit/<name>.md and docs/audit/<name>-attack.md.
  Running code, the CLI, the app, tests and the eval is encouraged. Do not run `make warm`.
- **Evidence over opinion:** a file:line, a command you ran and its output, a number (latency, accuracy, calls).
- **Trace real requests end to end** for each role, at least:
  - "How are we doing in LATAM this quarter?"
  - "Is supply safe for Plant-B?"
  - "Xarelto net sales in Germany"
  - REQ-0001 (Nubeqa global)
  - one request of your own that should break something.
- **Phase 1 is blind:** do not open another person's audit until yours is pushed.

## Report format: docs/audit/<name>.md
For every node (short for nodes outside your stretch, deep inside it):
1. **In / out:** what goes in, what comes out.
2. **How it works now:** file:line.
3. **Assumption:** the "because it works" decision behind it.
4. **Attack:** how it fails or misleads (repro + result).
5. **Optimise:** faster, cheaper, simpler, more accurate.
6. **0 to 1:** the idea that would make this node ours and unlike any other team's.
7. **Effort / impact:** S/M/L and hours / what changes for a Bayer user or a judge.
8. **Verdict:** keep / improve / replace.

Then three end-to-end sections:
- **End to end:** does the chain work for each role? Where does it break, where is it slow, how many LLM calls?
- **Top 3 changes**, ranked.
- **One bold idea** for the chain as a whole.

## Process
1. **Audit, blind:** write and push docs/audit/<name>.md. Then:
   - `tools/coord.py status --now "AUDIT DONE: docs/audit/<name>.md"`
   - `tools/coord.py say all "AUDIT DONE ..." --kind done`
   Target 20:00.
2. **Attack, once all four audits are pushed:** read the other three and write docs/audit/<name>-attack.md.
   - For each proposal you disagree with: why, with evidence, and a better alternative.
   - For each one you agree with: say so in one line.
   - Steal and combine ideas: the best solution can be a mix.
   - Post `ATTACK DONE` the same way. Target 20:45.
3. **Decide, together:**
   - Gajus's Claude drafts docs/audit/DECISION.md from the four audits and four attacks: one ranked list of changes, each with owner, effort and expected effect.
   - Each Claude replies on the board within 20 minutes: ok, or objection with evidence.
   - Gajus decides the contested items.
   - Only then does the build resume, from DECISION.md. Target 21:15.

## Rule added 18:50 (Gajus): more ideas, no duplicates
- Every audit carries **more optimisation ideas and more bold ideas**, not just the top 3 and one bold idea. Aim for
  at least 5 optimisations and 3 bold ideas beyond your top 3.
- **Duplicates go to the earlier publisher.** Order is the push time of the commit that first contains the idea.
- If your idea duplicates one that was pushed earlier, it does not count: cite the earlier one and add a new idea in
  its place.
- The later you publish, the more existing ideas you have to read and go beyond. Check the audits already on main
  before you push.
- The same applies to the attack files: new alternatives, not restated ones.
