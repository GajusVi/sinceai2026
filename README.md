# SinceAI 2026 workspace

Decision-layer scaffold: company data in, a scored queue with evidence out, approve/reject, audit trail.

## First run (once, on good Wi-Fi)
```bash
cd ~/SinceAI2026 && ./setup_mac.sh --all
```
Then add one API key to `.env` and run `make ping`.

## Daily commands
| Command | What |
| --- | --- |
| `make ui` | decision screen, live LLM |
| `make demo` | same screen, replays cached outputs, no network |
| `make eval` | hold-out accuracy, F1, misses |
| `make warm` | record live outputs into demo/cache (Saturday) |
| `make api` | FastAPI on :8000, docs at /docs |
| `make hack` / `make unhack` | keep the Mac awake, network check |

## Friday edits, in order
1. `backend/pipeline.py`: `LABELS`, `URGENT`, prompt.
2. `.env`: `USER_ROLE=`.
3. `backend/models.py`: rename `Item` to the company's noun, add fields the UI needs.
4. `frontend/app.py`: `TITLE`, `TAGLINE`.
5. `demo/inputs.jsonl`: 5-10 real inputs (one wow, one messy, one edge case).
6. `eval/holdout.jsonl`: 20-50 labelled examples, before tuning anything.

Files: `CLAUDE.md` (architecture, rules) · `NOTES.md` (team, decisions) · `CHALLENGE_PICK.md` · `submission/` · `docs/`.
