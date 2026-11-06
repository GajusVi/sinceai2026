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
- Martynas -> Margiris (steward/linking.py): "first sales" must CLARIFY, but the stem "sales" (net_sales synonym) matches inside it. Add a phrase blocklist/longest-match guard for ambiguous phrases (first sales, forecast, coverage, performance, readiness).
- Gajus → Martynas: catalog.py split for the data-pack path, OK'd by Martynas, committed.
- Margiris -> Martynas (steward/models.py): add `kpi_id: str = ""` and `variants: list[{kpi_id, kpi_name, definition_status, approval_status, owner_id}] = []` to MetricDefinition (catalog/bayer/metrics.json already has them). Until then steward/linking.py `kpi_index()` reads the JSON directly; I will switch to the fields once they exist.
- Gajus → Margiris: (1) L5 NOT_FEASIBLE: tests/bi_steward/golden_datapack.json has 'batch yield' as a known_gap (xfail); remove the key when it works. (2) Rules parser flags ordinary words as unmapped (finance, comparing, performance, status, Power BI, Tableau, workbook, replacement), so 5 of the 6 request templates I tried answer CLARIFY (not run on all 150 yet). Needs a stopword/phrase list, or the LLM parser, before the hold-out (D5).

## Decisions
- 2026-11-06 21:45: BI Steward (Donatas's bi-steward repo) merged in as the app: steward/, prompts/, catalog/, frontend/steward_app.py, tests/bi_steward/. `make ui`/`make demo` now open it; old scaffold = `make ui-old`. No new installs needed (all deps already in requirements.lock.txt). Rest of steward/ ownership to assign Sat 09:00.
- 2026-11-06: Bayer data pack committed to data/bayer/ (synthetic, built for builders, private repo) so everyone has it on git pull. Exception to the data/brief/ rule; move out if the team disagrees.
- 2026-11-06 22:00: Build plan in docs/BUILD_PLAN.md (S1 logic lock 22:15, contracts by 24:00, core on real data by Sat 03:00, freeze Sun 02:00, submit Sun 08:00).
- 2026-11-06 22:30: RETIRE rule changed from '< 1,000 views' to relative, age-aware rule (BUILD_PLAN 2.2): >= 3 months old, bottom-20% monthly users since creation, no subscriptions/dependants, plus duplicate or no owner; human-approved, 30-day reversible archive.
- 2026-11-06 22:50: Trap 18 logged: asset name suffixes contradict market_scope (67 of 88). Scope comes from fields only; mismatch = data-quality flag.
- 2026-11-06 23:15: Ownership = role + person. Inactive/missing owner → REASSIGN_OWNER: same role+scope successor (23 assets), same role other scope (21), role vacant → BI Platform Owner (21, + 21 null owners). Successor must accept; journaled. Trust: active 0.20, role still staffed 0.10, vacant 0.
- 2026-11-07 00:05: Extra hour assigned (docs/tasks/*.md EXTRA): Martynas T5 MetricDefinition.kpi_id/variants + T6 intent labels (data/holdout/); Donatas T4 Orphan rescue tab; Gajus T3a request-intake conflict check; Margiris's LLM-prompt part moved to Sat. New `make bayer` = app on the data pack.
- 2026-11-06 23:45: S1 accepted as proposed (BUILD_PLAN section 2). Task briefs per person in docs/tasks/. Loader goes in steward/datapack.py, so no catalog.py handover needed.
- 2026-11-06 23:40: Tonight's shift revised (BUILD_PLAN 'TONIGHT'): Martynas + Donatas to 01:00 on C1/C4/D2/D3 and A1 shell/A7; Gajus + Margiris to 03:00 on D1 loader, C2/C3, L1-L3, D4. Martynas hands steward/catalog.py to Gajus for tonight only.
- 2026-11-07 00:20: T1 done (Martynas): steward/models.py gains UsageMonth, Evidence, Artifact data-pack fields, CONSOLIDATE/NOT_FEASIBLE, Decision.evidence/flags, ParsedQuestion.unmapped_terms/conflicts; all defaulted, 28 tests green.
- 2026-11-07 00:50 (Martynas) handover. DONE: T1 models (pushed 00:20); T2 steward/spec.py + test_spec.py; T3 catalog/bayer/metrics.json (18 canonical, 38 variants, synonyms per brief); T4 catalog/bayer/dimensions.json + regions.json; generator data/build_bayer_dictionaries.py; tests green. HALF-DONE: nothing; Gajus must review synonyms. NEXT: Sat 08:00 D5 hold-out labelling with Margiris, then D6 preview. Note: a cp1252-encoded untracked demo/cache file broke smoke tests; moved aside, root cause unknown.
- 2026-11-07 Gajus: T1+T2 done and committed: steward/intent.py (Intent, is_complete, should_stop, to_parsed_question), steward/datapack.py (360 Artifacts from the xlsx; opt in with STEWARD_CATALOG=datapack, uses catalog/bayer/), catalog.py split into apply_changes/read_json. Name-vs-scope rule flags 71 assets (doc says 67). Successor tiers 23/21/21-vacant and 16 certified-on-failed-refresh match the log.
- 2026-11-07 Gajus: T3 done: steward/requests.py (load_requests, context_conflicts) + Steward.ask(text, context=None): text vs request metadata (product, market/region) -> ParsedQuestion.conflicts -> CLARIFY. Reproduces trap 1 (65 of 75). tests/bi_steward/golden_datapack.json + test_golden_datapack.py: REQ-0001 with metadata -> CLARIFY, without -> CREATE, 'Inventory Coverage Mgmt' -> CLARIFY with KPI-016 canonical and 017/018/019 variants, vague -> CLARIFY, batch yield -> NOT_FEASIBLE as known_gap. Not locked on purpose: exact best asset for net-sales questions (engine picked a Tableau 'promoted' asset over a Power BI one; verify trust ranking with Margiris first).
- 2026-11-06: Next P0 = data-pack loader replacing catalog/ sample; KPI-id matching; unrecognised terms count against coverage (fixes false REUSE on REQ-0001).
- 2026-11-05: scaffold = FastAPI + Streamlit + SQLite audit log; LLM via OpenAI-compatible client (provider by env).

## Questions for the company (Sat 09:00-12:00 Q&A)
-

## Cut list (Sat 12:00 checkpoint)
-
## Webhook test
- Fri 6 Nov: GitHub → Discord #github-feed test commit
- 2026-11-07 00:50 Donatas handover. Done: T1 chat Ask tab (st.chat_input + history), expert-mode toggle (no behaviour), evidence cards (FAKE_EVIDENCE labelled "Sample evidence" until decision.evidence exists), CONSOLIDATE/NOT_FEASIBLE titles, claimed-vs-observed placeholder row; T2 Reset demo; T3 tests/bi_steward/test_app.py (AppTest chat + reset twice). Half-done: claimed-vs-observed shows "not wired yet"; approve/reject only for REUSE/EXTEND/CREATE. Next: wire to the real engine + A3 KPI card (Sat after Q&A). Note: `make lint` auto-fixes files of other owners (docs/vendor, steward/decision/minhash.py); run ruff on your own files only.
- 2026-11-07 Margiris: T1 BackendClient (STEWARD_LLM_PROVIDER=backend; auto = Claude key, else backend if configured). T2 unmapped_terms + STOPWORDS in steward/config.py; unmapped/conflicts -> CLARIFY with blocker Evidence. 'trial/logistics/footprint' are stopwords only because the sample catalog lacks synonyms; drop when the data-pack loader lands. tests/test_smoke.py has 2 pre-existing Windows failures (UnicodeDecodeError), not from this work.
- 2026-11-07 Margiris: T3 done on KPI ids: `artifact_covered_metrics` (kpi_ids path; formula path kept when kpi_ids empty), variant KPI -> MetricConflict + Evidence RULE-002 suggesting the canonical id (capped at 10 per decision). Linker guard AMBIGUOUS_PHRASES ('first sales'...). Finding: REQ-0001 on the data pack from text alone is CREATE (all 3 metrics exist, no asset has all), not CLARIFY; CLARIFY needs the text-vs-product_context conflict set in `ParsedQuestion.conflicts` by the request/intent layer (Gajus). Tests: tests/bi_steward/test_kpi_matching.py.
- 2026-11-07 Margiris: search recall fix for the data pack: steward/search/ now reads metrics via kpi_ids (artifact_covered_metrics) and passes the top 40 hits (was 8) to the engine. REQ-0001 text-only on the pack is now EXTEND (best AST-0143 60%; AST-0015 and AST-0335 are alternatives), not CREATE. Open: AST-0143 is EMEA-only but the request says 'global' and the parser has no market filter, so scope mismatch is not caught yet. Gajus's intake conflict still decides CLARIFY first.
- 2026-11-07 (Martynas): MetricDefinition now has kpi_id, unit and variants (new MetricVariant model), all defaulted; catalog/bayer/metrics.json validates (18 metrics, 38 variants). Margiris: kpi_index() can switch to the fields. 52 tests green.
- 2026-11-07 (Martynas) T5+T6. T5 done: MetricDefinition kpi_id/variants/unit + MetricVariant (e96f05a), test added (inventory_coverage KPI-016 with KPI-018/019 variants).
- T6 done: data/holdout/requests_intent.jsonl (40 requests, 4 per template, 20 conflicts / 20 clean-or-silent), made by data/build_holdout_intent.py from the TEXT only, all 40 lines checked by hand. The same rules give 75 requests naming a product and 65 conflicting, which matches the data-pack doc.
- T6 conventions (Margiris/Gajus please confirm): products are names ("Nubeqa") like Intent.products; expected_markets is always [] (no text names a country); expected_grain is "month" everywhere (Intent default, no text says quarter); "oncology brands" = Nubeqa+Hyrnuo; ambiguous words (performance, first sales, launch readiness) and supply risk map to NO metric; product_context "All Pharma" counts as a conflict when the text names a product, and a specific product counts as a conflict when the text says Bayer Pharma; region or country context counts as a conflict when the text says "global", and a region context conflicts with "country-level". Templates 6 and 9 have no clean row (no request there has matching metadata).
