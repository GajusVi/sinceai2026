# BI Steward

Bayer hackathon: "AI can generate dashboards faster than ever. The next breakthrough may be knowing what deserves to exist at all."

BI Steward is an assistant that, for any business question, first looks for what already exists in the company and only then allows something new to be created. It answers every question with one verdict:

| Verdict | When |
|---|---|
| **REUSE** — use as is | An existing report fully answers the question and can be trusted |
| **EXTEND** — improve it | A report almost fits: a filter, breakdown, metric, owner or certification is missing |
| **CREATE** — build a new one | No report contains the required metric with the official formula |
| **CLARIFY** — ask for clarification | The question contains no metric from the dictionary |

On top of any verdict, the system warns about **metric conflicts**: when a report's "Revenue" is actually calculated with a different formula than the official one. The catalog changes only when a human clicks "Approve". Every decision is written to a journal.

## Quick start

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                                  # dependencies
uv run pytest                            # 22 tests, including the golden questions
uv run streamlit run app.py              # UI at http://localhost:8501
uv run python -m steward "What is herbicide revenue in LATAM vs plan for Q3?"
```

No language model key is needed: without one, the question is parsed using the dictionary and the explanation is built from a template. To connect Claude:

```bash
cp .env.example .env                     # and fill in ANTHROPIC_API_KEY
uv sync --extra llm
uv run --env-file .env streamlit run app.py
```

The default model is `claude-haiku-5-5`; set `STEWARD_LLM_MODEL` to use another. Claude has no embeddings API, so search "by meaning" stays offline. Gemini can be used instead of Claude: `uv sync --extra gemini`, `GEMINI_API_KEY` and `STEWARD_LLM_PROVIDER=gemini`.

`STEWARD_AS_OF=2026-11-06` pins "today" for freshness checks: the dates in the sample catalog are set relative to that day. Approved changes and the journal are written to `data/`. To reset the catalog, delete the files in `data/`.

The UI and documentation are in English. The metric dictionary also holds Russian synonyms, so questions can be asked in Russian too.

## Structure

```
catalog/                  sample catalog: what already exists in the company
  artifacts.json          18 BI artifacts with duplicates, conflicts and "dead" reports
  metrics.json            dictionary of official metrics: formula, owner, synonyms
  dimensions.json         breakdowns (region, product...) and their values
steward/
  models.py               data models: Artifact, ParsedQuestion, Decision...
  catalog.py              loads the catalog and approved changes from data/
  linking.py              links words in the question to official metrics and dimensions
  query_parser.py         step 2: question → metrics, filters, breakdowns, period (rules or LLM)
  llm.py                  LLM clients: Claude (default) and Gemini
  search/                 step 3: candidate search
    lexical.py            by words (BM25)
    semantic.py           by meaning (offline stand-in or Gemini embeddings)
    structural.py         by shared metrics and breakdowns
    rrf.py                merges the three rankings
  decision/               step 4: verdict
    signals.py            question coverage and report trust
    conflicts.py          one metric, different formulas
    engine.py             REUSE / EXTEND / CREATE / CLARIFY rules
    minhash.py            text similarity for duplicate detection
  explain.py              step 5: explanation (template or LLM)
  governance.py           step 6: approval, rejection, journal, catalog writes
  health.py               catalog health: duplicates, stale, no owner
  pipeline.py             the Steward class: the whole flow
prompts/                  LLM prompts in YAML
app.py                    Streamlit UI
tests/                    tests; golden_questions.json is the verdict contract
docs/                     documentation
```

## Documentation

- [Architecture](docs/architecture.md): diagrams, components, decision rules, data model, what was taken from `zenzap-ai-search`.
- [Work plan](docs/work-plan.md): tasks by role, order, definitions of done, team rules.
- [Demo script](docs/demo-script.md): what to show the jury and in what order.

## Team rule

`tests/golden_questions.json` is a contract: which question gets which verdict. If you change the catalog, rules or prompts, run `uv run pytest`. If a verdict changed on purpose, update the file in the same commit and explain why.
