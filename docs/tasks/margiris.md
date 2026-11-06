# Margiris: tonight 00:05 → 03:00 (LLM plumbing, no silent drops, KPI-id matching)

Tell your Claude Code: "Do docs/tasks/margiris.md. Read CLAUDE.md, docs/BUILD_PLAN.md section 2 and docs/challenge/03_DATA_PACK.md first."
Your files tonight: steward/llm.py, steward/query_parser.py, steward/linking.py, steward/decision/, prompts/ (excl. interview.yaml).
Martynas adds the model fields (`ParsedQuestion.unmapped_terms`, `Decision.evidence`, `Evidence`) by ~00:30: pull then.

## T1 (L1, 00:05-00:45) LLM through the existing client, no new installs
`steward/llm.py`: add a `BackendClient` (provider "backend") that reuses `backend/llm.py` + `backend/config.py`
(Gemini / Ollama / Aitta via the OpenAI-compatible client already in the lockfile):
- `generate_json(prompt)`: call `backend.llm.complete_json(system, user, schema)` with a permissive schema
  (`class _AnyJSON(BaseModel): model_config = ConfigDict(extra="allow")`) and return `.model_dump()`.
  This gives you validation, one repair retry and the demo/cache replay for free.
- `generate_text(prompt)`: `backend.llm._client().chat.completions.create(...)` with the model from `get_settings().resolved()`.
- `get_llm`: `STEWARD_LLM_PROVIDER=backend` → BackendClient; `auto` = Claude if ANTHROPIC_API_KEY, else backend if
  `backend.config.get_settings().llm_ready()`, else None. `STEWARD_USE_LLM=off` still forces rules.
Done when: with the team .env (LLM_PROVIDER=gemini) `.venv/bin/python -m steward --json "Net revenue by region for Q3"` shows `"parser": "llm"`;
with STEWARD_USE_LLM=off it shows rules; `make test` green.

## T2 (L3, 00:45-01:45) no silent drops
- Rule parser: every content word not covered by a matched term, a period, or a stopword list goes to `unmapped_terms`
  (stopwords: what, is, the, in, for, by, vs, and, of, a, an, me, our, we, need, show, create, build, new, please, can, you, dashboard,
  report, view, management, monthly, global, country, level...). Keep the list in steward/config.py.
- LLM parser prompt (`prompts/query_parser.yaml`): also return `"unmapped": [...]`; validator keeps them (it currently drops unknowns silently).
- Engine: `unmapped_terms` or `conflicts` non-empty → CLARIFY, reason lists the terms, Evidence(rule_id=None, severity="blocker").
- Test (add to tests/bi_steward/test_parser.py): REQ-0001 text "Create a global Nubeqa dashboard showing sales growth, forecast variance and
  market access by country." on the sample catalog → CLARIFY, not REUSE. All 8 existing golden questions stay green
  (tune stopwords, don't change goldens).

## T3 (L2, 01:45-03:00, after Gajus's loader lands ~01:30) KPI-id matching
- Metric present on an asset ⇔ asset.kpi_ids contains the canonical kpi_id from `catalog/bayer/metrics.json`.
- Asset uses a variant (duplicate_candidate / local_variant / definition_conflict) → `MetricConflict` + Evidence(rule_id="RULE-002"),
  and the metric does NOT count as covered.
- Keep the formula path for the sample catalog (branch on `artifact.kpi_ids` being empty) so old tests stay green.
- Test: an asset with KPI-018 or KPI-019 is a conflict for inventory coverage; canonical KPI-016 suggested.
## 03:00 checkpoint with Gajus: app on data pack, REQ-0001 → CLARIFY. Saturday: L4, L5, then eval with Martynas.
