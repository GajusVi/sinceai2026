# Donatas: tonight 00:05 → 01:00 (screen shell)

Tell your Claude Code: "Do docs/tasks/donatas.md. Read CLAUDE.md and docs/BUILD_PLAN.md section 0 and 2 first."
File: `frontend/steward_app.py` (yours). Don't wait for anyone: use a fake evidence list until `decision.evidence` exists.

## T1 (A1 shell) chat-style Ask tab
- Replace the text_input + Ask button with `st.chat_input`; keep a history in `st.session_state.messages`
  (user turn = question, assistant turn = one-line verdict summary). Latest result still renders below with `render_result`
  (keep approve / reject / reason / journal exactly as they are).
- Sidebar: `st.toggle("Expert mode: skip the interview")` stored in session state (no behaviour yet; Gajus's interview uses it).
- Evidence cards under the verdict: one card per item with claim, rule id badge (e.g. RULE-003), record ids, value; severity colour
  (info / warning / blocker). Source: `getattr(decision, "evidence", [])`; if empty show `FAKE_EVIDENCE` (3 dicts in the C3 shape:
  claim, rule_id, record_ids, value, severity) with a small "sample evidence" caption so nothing fake is ever unlabelled.
- Add titles for the new verdicts so the screen never KeyErrors: CONSOLIDATE "Consolidate duplicates", NOT_FEASIBLE "Not possible with governed data"
  (use `VERDICT_TITLES.get(verdict, verdict.value)`).
- "Claimed vs observed" placeholder row on the recommended report (lifecycle label vs usage) – fill later.

## T2 (A7) Reset demo
Sidebar button "Reset demo": delete `data/steward/catalog_changes.json` and `data/steward/journal.jsonl` if present,
`st.cache_resource.clear()`, clear session state, `st.rerun()`.

## T3 smoke test `tests/bi_steward/test_app.py`
Streamlit AppTest: open the app with `STEWARD_USE_LLM=off`, send one chat message, assert no exception.
This makes the pre-push hook protect the screen for everyone.

Done when: `make demo` shows the chat, a fake-evidence card, reset works twice, `make test` green, pushed.
## 00:55 handover
Push, then 3 lines in NOTES.md: done / half-done / next. Saturday: 08:30 S2, 09:00 Q&A with Gajus, then wire to the real engine + A3 KPI card.

---
# EXTRA (Sat 00:05 → 01:00), added after your first handover
## T4 (A4) Orphan rescue tab, on the real data pack
Run with `make bayer` (Windows `.\run.ps1 bayer`) = STEWARD_CATALOG=datapack. New tab "Orphan rescue" in frontend/steward_app.py:
- Asset picker (default **AST-0091 "Hyrnuo Growth - US"**), searchable by id or name.
- Panels, all from `steward.catalog.artifact(id)` fields (already loaded by Gajus's loader):
  Owner: owner_id, role, scope, **status** (inactive in red), `successor_candidates` with names from the Owners data;
  Trust: endorsement, model refresh_status (warning/failed in amber/red), platform;
  Usage: `st.line_chart` of monthly unique_users from `usage` (months since creation only);
  Signals + data_quality flags as small chips; "Claimed vs observed": `lifecycle_claimed` next to the usage tier,
  and a name-vs-scope note when data_quality has the mismatch flag.
- Buttons "Propose successor" and "Retire candidate": for now they only write a journal entry via `steward.governance`
  (reason required), clearly labelled "proposal". Real logic comes from Margiris's rules on Saturday.
- If the catalog is the sample one (no `owner_status`), show "Run make bayer to load the Bayer data pack" instead of crashing.
- Extend tests/bi_steward/test_app.py: the tab opens on the data pack with AST-0091 without exceptions.
Done when: AST-0091 shows inactive owner, successors, refresh warning, usage chart. Push + 3 lines in NOTES.md by 00:55.
