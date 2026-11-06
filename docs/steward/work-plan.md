# Work plan

## Where we are

The skeleton works end to end: question → parsing → search → verdict → explanation → approval → journal. Plus the catalog health screen. Everything runs without a language model key, and all 22 tests pass.

Already done:

- [x] Sample catalog: 18 reports, 12 metrics, 10 dimensions, planted duplicates and conflicts
- [x] Question parsing by dictionary and via Claude, with validation of the model's answer
- [x] Search by words, meaning and structure, merged with RRF
- [x] Coverage, trust, conflicts, REUSE / EXTEND / CREATE / CLARIFY rules
- [x] Explanation by template and via Claude
- [x] Approval, rejection, journal, new versions in the catalog
- [x] Catalog health: duplicates, stale, no owner, retirement candidates
- [x] Streamlit UI with four tabs
- [x] 8 golden questions; tests for the parser, search, approval and health
- [x] Everything in English; the dictionary also understands Russian questions

The next task is not to write the system but to make it convincing: realistic data, a clear screen and a rehearsed demo.

## Roles

Planned for 4 people. With three, roles C and D merge.

| Role | Responsible for | Main files |
|---|---|---|
| **A. Data** | A realistic Bayer catalog, metric dictionary, golden questions | `catalog/`, `tests/golden_questions.json` |
| **B. Search and decision** | Search quality, verdict rules, catalog health | `steward/search/`, `steward/decision/`, `steward/health.py` |
| **C. Language model** | Question parsing and explanation via Claude, prompts | `steward/llm.py`, `steward/query_parser.py`, `steward/explain.py`, `prompts/` |
| **D. UI and pitch** | Screen, demo script, slides | `app.py`, `docs/demo-script.md` |

## Order

Tasks have a priority:

- **P0** — no demo without it;
- **P1** — strengthens it a lot;
- **P2** — if time allows.

Within a priority, roles work in parallel.

### Stage 1. Setup and agreements (everyone, first hour)

| # | Task | Who | Done when |
|---|---|---|---|
| 1.1 | Everyone runs `uv sync`, `uv run pytest`, `uv run streamlit run app.py` | all | everyone has green tests and the screen opens |
| 1.2 | Walk through the main question in the UI and read `docs/architecture.md` | all | everyone can explain steps 1–6 in their own words |
| 1.3 | Get an Anthropic API key and put it in `.env` (not in git) | C | `uv run --env-file .env python -m steward --json "..."` shows `parser: llm` |
| 1.4 | Agree on the final demo script: which 3 questions we show | D + all | list of questions in `docs/demo-script.md` |

### Stage 2. Data (role A)

| # | Priority | Task | Done when |
|---|---|---|---|
| 2.1 | P0 | Grow the catalog to 30–40 reports across all Bayer divisions: Crop Science, Pharma, Consumer Health, plus shared Finance, Supply Chain, HR, Sustainability | every division has 5+ reports, including bad ones |
| 2.2 | P0 | An honest card for every new report: formulas, breakdowns, hard filters, owner, dates, views | `uv run pytest` is green |
| 2.3 | P0 | Add problems: 2–3 new formula conflicts, 3–4 duplicates, 2 reports with no owner, 2 stale ones | the "Catalog health" screen shows them |
| 2.4 | P1 | Grow the metric dictionary to 15–20 metrics with English and Russian synonyms | new synonyms covered by a test in `test_parser.py` |
| 2.5 | P1 | 15+ golden questions: 3+ per verdict, plus 3 questions with a conflict | all in `golden_questions.json`, tests green |

How to add a report: copy a card in `catalog/artifacts.json`. Metric formulas must match `metrics.json` character for character, otherwise the metric does not count. That is also how you plant a conflict.

### Stage 3. Search and decision (role B)

| # | Priority | Task | Done when |
|---|---|---|---|
| 3.1 | P0 | Run all golden questions after the catalog grows; fix rules or synonyms | all golden questions green |
| 3.2 | P0 | Check that the best report for every question is in the top 3 of search | top-3 test for all golden questions |
| 3.3 | P1 | EXTEND by adding a metric: the report exists and all breakdowns match, but the metric is missing | a golden question for this case |
| 3.4 | P1 | Score breakdown: show what coverage and trust are made of | `Candidate` stores the breakdown and the UI shows it |
| 3.5 | P1 | Retirement as an action: a "Propose retirement" button, journal entry, `retired` status | the report disappears from search after approval |
| 3.6 | P2 | Real embeddings (Gemini or Voyage AI) and a search quality comparison with the offline version | a short before/after table for the pitch |
| 3.7 | P2 | Lineage: link reports through `source_tables`, warn "this report breaks if table X changes" | a tab or block in the UI |

### Stage 4. Language model (role C)

| # | Priority | Task | Done when |
|---|---|---|---|
| 4.1 | P0 | Check `LLMParser` on all golden questions | same verdicts as the rule-based parser |
| 4.2 | P0 | Free-form wording the rules miss: "how much did we make on weed killers in Brazil" | 5+ such questions work with Claude |
| 4.3 | P1 | Improve `prompts/explain.yaml`: short, businesslike, no invented facts | 3 explanations you would happily show the jury |
| 4.4 | P1 | Draft specification on CREATE: title, metrics, breakdowns, sources, owner | shown on screen before the "Create" button |
| 4.5 | P2 | Clarifying question on CLARIFY: the model proposes 2–3 metrics the user may have meant | option buttons in the UI |
| 4.6 | P2 | A separate test suite with the model that does not run in plain `pytest` | `pytest -m llm` |

Rule: the model makes no decisions. It parses the question and writes text. The rules choose the verdict.

### Stage 5. UI and demo (role D)

| # | Priority | Task | Done when |
|---|---|---|---|
| 5.1 | P0 | Decision screen as in the diagram in `docs/architecture.md`: big verdict, explanation, visible conflict, two buttons | an outsider understands it without explanation |
| 5.2 | P0 | A "Reset demo" button that clears `data/` | the demo can be run several times in a row |
| 5.3 | P0 | Demo script and timing | `docs/demo-script.md` fits the allotted time |
| 5.4 | P1 | Value metric on the "Health" screen: how many reports were not created, how many duplicates were found | a number for the final slide |
| 5.5 | P1 | Slides: problem, solution, demo, architecture, what's next | 5–7 slides |
| 5.6 | P2 | Architecture diagram from `docs/architecture.md` in the slides | one picture per slide |

### Stage 6. Final (everyone)

| # | Task | Done when |
|---|---|---|
| 6.1 | Code freeze: only fixes after it | a demo commit is tagged |
| 6.2 | Two full demo runs on a clean `data/` | each run without failures |
| 6.3 | Backup plan: demo without internet and without a key | everything works with `STEWARD_USE_LLM=off` |
| 6.4 | Answers to jury questions | see below |

## Checkpoints

| When | What must work |
|---|---|
| End of stage 1 | It runs for everyone, everyone understands the architecture |
| Midpoint | Catalog grown, 15 golden questions green, Claude connected |
| 4 hours before submission | The demo runs end to end, slides ready, freeze begins |

## Working rules

- One task, one branch, one small PR. Task number in the name, e.g. `2.3-catalog-conflicts`.
- Before a PR: `uv run pytest`. Red tests are never merged.
- If a golden question's verdict changes, update `golden_questions.json` in the same PR and say why.
- Decision thresholds live only in `steward/config.py`; do not scatter them through the code.
- Keys only in `.env`, which is in `.gitignore`.
- `catalog/` is the source of truth for the demo. `data/` is local state and is not committed.

## Jury questions to prepare for

| Question | Short answer |
|---|---|
| How is this better than plain catalog search? | Search finds something similar. We decide whether it answers the question and whether it can be trusted, and we check the formulas |
| Why doesn't the model make the decision? | The decision must be explainable and identical every time. The model understands the question and writes the text |
| How would it connect to a real catalog? | Replace `catalog/*.json` with loading from the Power BI, Tableau or Collibra API. The rest of the code works with the `Artifact` model |
| What about thousands of reports? | Port the hybrid search with Qdrant and the reranker from `zenzap-ai-search`. The decision rules stay the same |
| Who is accountable for the decision? | The domain owner. The catalog does not change without their approval, and every decision is journaled |
| How does this reduce chaos rather than just not adding to it? | The health screen finds duplicate, stale and ownerless reports and proposes retiring them |
