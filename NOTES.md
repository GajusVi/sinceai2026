# NOTES: who does what, decisions, open questions

## Team
Lead (picks the challenge in sinceai.app at 17:00, merges to main): Gajus

| Who | GitHub | Laptop | LUMI/Aitta | Owns | Files they edit |
| --- | --- | --- | --- | --- | --- |
| Gajus | GajusVi | Mac Intel 2020 | yes | Product + pitch: challenge pick, user, one-sentence demo, company Q&A, euro case, 4-min pitch, judge Q&A | NOTES.md, README.md, docs/ |
| Margiris | MargirisRakutis | Windows | yes | Model + proof: labels, prompts, held-out set, eval numbers, confidence check, euro formula inputs | backend/pipeline.py, backend/llm.py, eval/ |
| Martynas | Paradox-Mrt | Windows | no | Data: company files to clean records, data quality, labelling the held-out set with Margiris | backend/ingest.py, backend/models.py, data/ |
| Donatas | dpaulauskas0-cmd | Mac Air M4 | no | App + demo + submission: Streamlit screen, demo mode and cache (warm), 60-90 s video, screenshots, sinceai.app page | frontend/, demo/, submission/ |

Backups: Gajus covers Donatas's submission page on Sunday morning; Margiris runs any LUMI/Aitta job.
All on Claude Pro: heavy Claude Code sessions go to the owner of that area only; think and plan in claude.ai chat.
Git: edit only your own files where possible; `git pull --rebase` before every `git push`; small commits; never commit .env or data/brief/.

## Challenge ranking (rev. Thu 5 Nov 23:25, LLM council round 2: Opus/Sonnet/Haiku; no domain expertise; keep IP)
Select in this order: 1. Bayer  2. Lindstrom  3. Fonecta  4. Europress
Take Lindstrom first if Bayer looks full or crowded at selection.
Then: 5. FORCIT  6. Meyer Turku  7. Elisa  8. Apetit  9. Turku Energia  10. Business Turku  11. Valmet  12. Traficom  13. TrustED
Excluded (IP goes to company): Takomo Golf, DNA

## One-sentence demo (Fri 21:30 latest)
For [user], takes [input], returns [output], so they can [benefit].

## Requests (change needed in someone else's file: who asks, owner, what)
-

## Decisions
- 2026-11-06 21:45: BI Steward (Donatas's bi-steward repo) merged in as the app: steward/, prompts/, catalog/, frontend/steward_app.py, tests/bi_steward/. `make ui`/`make demo` now open it; old scaffold = `make ui-old`. No new installs needed (all deps already in requirements.lock.txt). Rest of steward/ ownership to assign Sat 09:00.
- 2026-11-06: Bayer data pack committed to data/bayer/ (synthetic, built for builders, private repo) so everyone has it on git pull. Exception to the data/brief/ rule; move out if the team disagrees.
- 2026-11-06 22:00: Build plan in docs/BUILD_PLAN.md (S1 logic lock 22:15, contracts by 24:00, core on real data by Sat 03:00, freeze Sun 02:00, submit Sun 08:00).
- 2026-11-06 22:30: RETIRE rule changed from '< 1,000 views' to relative, age-aware rule (BUILD_PLAN 2.2): >= 3 months old, bottom-20% monthly users since creation, no subscriptions/dependants, plus duplicate or no owner; human-approved, 30-day reversible archive.
- 2026-11-06: Next P0 = data-pack loader replacing catalog/ sample; KPI-id matching; unrecognised terms count against coverage (fixes false REUSE on REQ-0001).
- 2026-11-05: scaffold = FastAPI + Streamlit + SQLite audit log; LLM via OpenAI-compatible client (provider by env).

## Questions for the company (Sat 09:00-12:00 Q&A)
-

## Cut list (Sat 12:00 checkpoint)
-
## Webhook test
- Fri 6 Nov: GitHub → Discord #github-feed test commit
