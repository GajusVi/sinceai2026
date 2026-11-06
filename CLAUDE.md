# CLAUDE.md: read this first

SinceAI 2026 (Turku, 6-8 Nov). Build window Fri 19:30 to Sun 10:00. Submission must win without a pitch.

Event rules, timeline, prizes and credits: docs/sinceai/EVENT_FACTS.md. Slash commands /pick /brief /eval /warm /judge-qa /ship-check live in claude-setup/ until installed (see its README).
Shortlist and planned builds per challenge: docs/sinceai/TOP4.md. Real briefs and company data go in data/brief/ (read them first on Friday).

## Rules for working in this repo
- Read NOTES.md before starting; append a line to NOTES.md after every decision.
- Check docs/ (and docs/vendor/) before using a library or API parameter. Do not invent parameters.
- Small files, small diffs. Run `make test` after any change, `make eval` after any prompt/model change.
- Simplest working approach wins. Say so when a request does not fit the clock.
- Prior work (tag `pre-event`) and event work stay in separate commits.

## Challenge: Bayer "Build Less, Build Better: AI for Governed Analytics" (locked Fri 6 Nov)
Build plan (tasks per person, clock, cut order): docs/BUILD_PLAN.md.
Read first: docs/challenge/00_INDEX.md (brief, Panu's framework, data-pack traps, plan, repo review).
Data pack (synthetic, 360 BI assets): data/bayer/Bayer_Pharmaceuticals_SinceAI_2026_FINAL_Builder_Data_Pack.xlsx.
Scope: Bayer Pharma only. No Crop Science, no Consumer Health, no clinical/pharmacovigilance use cases.

## Active app: BI Steward (steward/, from Donatas's bi-steward repo)
```
question ─query_parser─▶ ParsedQuestion ─search (BM25+trigram+structure, RRF)─▶ hits ─decision/engine─▶ Decision
   REUSE | EXTEND | CREATE | CLARIFY  (+ metric-conflict warnings)  ─explain (template or LLM)─▶ text
human approve/reject ─governance.py─▶ data/steward/catalog_changes.json + journal.jsonl     health.py: duplicates, stale, no owner
```
- UI: frontend/steward_app.py (`make ui`, `make demo` = LLM off). CLI: `make ask Q="..."`. Tests: tests/bi_steward/.
- The verdict is rule-based code; the LLM only parses the question and rewrites the explanation. Thresholds: steward/config.py.
- tests/bi_steward/golden_questions.json is the verdict contract. Change a verdict on purpose -> update it in the same commit.
- Known gaps (see docs/challenge/06_REPO_REVIEW.md): catalog/ is still the invented sample (to be replaced by the data-pack loader),
  matching is by formula string (must become KPI id + definition_status), unrecognised terms are silently dropped (false REUSE).
- Design docs: docs/steward/architecture.md, work-plan.md (ignore its stage 2: the data pack replaces the invented catalog).

## Pre-event scaffold (backend/, frontend/app.py): legacy, kept until removed. `make ui-old`.
```
company files ──ingest.py──▶ Item ──pipeline.score──▶ Decision (label, priority, confidence, reason, evidence, action)
                                         │                  │
                                    llm.complete_json   rules_fallback (never crash)
                                         │
                               demo/cache/<hash>.json  ◀── DEMO_MODE replays this
Streamlit queue (frontend/app.py) ──approve/reject──▶ audit.py (SQLite, every output + every human action)
FastAPI (backend/main.py): /health /score /ingest /review /audit /audit.csv
```
- `backend/config.py`: env settings; `LLM_PROVIDER` switches anthropic | openai | aitta | featherless | gemini | ollama. `make models` lists model IDs.
- `backend/llm.py`: OpenAI client with base_url; JSON validated by Pydantic; one repair retry; caches every success.
- `backend/pipeline.py`: `LABELS` + prompt live here. Friday's first edit.
- `backend/retrieval.py`: fastembed (bge-small, ONNX, CPU) with TF-IDF fallback; numpy cosine. No vector DB.
- `eval/eval.py`: hold-out accuracy, macro F1, misses → `eval/results.json` → UI Proof tab.
- Streamlit imports the pipeline directly (one process on stage). FastAPI is for integrations and the README.

## Working as a team (four people, four Claude Codes, one repo)
- Who you work for: `git config user.name` (first word). Their area: OWNERS and the Team table in NOTES.md.
- Edit only files your person owns, plus shared files (anything not in OWNERS). For someone else's file, do not edit it:
  write the change you need under "Requests" in NOTES.md and tell your person to ask the owner.
- `backend/models.py` is the contract between data, model and app: never rename or remove a field without Martynas.
- Start of every session and before every push: `git pull --rebase`. Commit small, push often. Never force-push, never `git reset --hard`.
- A commit refused by the pre-commit hook means you touched another owner's file: unstage it, never use --no-verify yourself.
- `git push` runs the smoke tests first (pre-push hook). If it refuses, fix the failing test; never push with --no-verify yourself.
- Only Donatas runs `make warm` (rewrites demo/cache); only Margiris commits eval/results.json.
- Windows teammates: `.\run.ps1 <task>` instead of make; Python is `.venv\Scripts\python.exe`.

## Team board: how the four Claude Codes talk to each other (coord/, tools/coord.py)
The SessionStart and UserPromptSubmit hooks print the TEAM BOARD into your context when something changed:
teammates' status, open asks, answers to your asks, commits you are behind on. Act on it:
1. Behind origin/main → `git pull --rebase --autostash` before you edit anything.
2. After every push of real work → `.venv/bin/python tools/coord.py status --now "..." --done "..." --next "..." [--blocked "..."]`
   (one line each, plain words, commit ids for done work). It commits and pushes only coord/ (no test run).
3. You need someone else's file changed, a decision, or an OK → `tools/coord.py ask <name> "..." --files ...`,
   tell your person, then keep working on something else. Do not edit their file meanwhile.
4. An "ASK FOR YOU" appears → show it to your person word for word and ask them. Only after they answer in the chat:
   `tools/coord.py reply <id> ok|no|done "..."`. Never answer an ask on your own judgement.
5. "ANSWER TO YOUR ASK" appears → tell your person, act on it, then `reply <id> done "seen"` to clear it.
Windows: `.venv\Scripts\python.exe tools\coord.py ...`. Humans: `make board`.
6. Messages: `tools/coord.py say <name|all> "..." --kind <kind> [--re <msg-id>]`. Post, without being asked:
   - `done` to all when you finish a task: what changed, commit id, how to use it, what is still missing (5 lines max);
   - `breaks` to the author when their commit breaks your work: the error line, file, commit id, what you need;
   - `need` to someone you are waiting on (still need X by HH:MM, because Y); `question` when a decision is theirs;
   - answer a message with `--re <id>`. Show your person every MESSAGE FOR YOU and what you plan to do about it.
   Never paste secrets, .env values or long logs; put long detail in the message body or a commit.
7. Check the board yourself (`tools/coord.py brief --full`) before every push and when you finish a task:
   the hooks only fire when your person sends a prompt, not while you work or sit idle.
8. ESCALATE hard calls instead of deciding them: changes to a shared contract (steward/models.py, intent.py, spec.py),
   verdict rules or thresholds, a conflict between two owners, cutting or adding a feature, anything the build plan doesn't cover.
   `tools/coord.py say gajus "ESCALATE: <decision>. Options: A ..., B .... I recommend A because ..." --kind question`,
   tell your person, and work on something else until the answer arrives. Gajus decides (with his architect chat) and
   records it in NOTES.md; the answer comes back with `--re <id>`.

## Commands
`make ui` · `make demo` (LLM off) · `make ask Q="..."` · `make ui-old` · `make api` · `make eval` · `make warm` (record cache) · `make ping` · `make test` · `make lint` · `make hack`

## Machine constraints
- Intel MacBook (x86_64). No CUDA/MPS. torch is capped at 2.2.2 on Intel Macs and conflicts with numpy 2: don't add torch/sentence-transformers. Use fastembed or API embeddings.
- Local Ollama (llama3.2:3b) is a slow offline fallback only.

## Decisions log
See NOTES.md.
