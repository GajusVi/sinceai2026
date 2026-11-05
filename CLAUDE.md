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

## Architecture (decision layer)
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
- Only Donatas runs `make warm` (rewrites demo/cache); only Margiris commits eval/results.json.
- Windows teammates: `.\run.ps1 <task>` instead of make; Python is `.venv\Scripts\python.exe`.

## Commands
`make ui` · `make demo` (DEMO_MODE) · `make api` · `make eval` · `make warm` (record cache) · `make ping` · `make test` · `make lint` · `make hack`

## Machine constraints
- Intel MacBook (x86_64). No CUDA/MPS. torch is capped at 2.2.2 on Intel Macs and conflicts with numpy 2: don't add torch/sentence-transformers. Use fastembed or API embeddings.
- Local Ollama (llama3.2:3b) is a slow offline fallback only.

## Decisions log
See NOTES.md.
