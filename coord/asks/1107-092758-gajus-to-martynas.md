id: 1107-092758-gajus-to-martynas
from: gajus
to: martynas
status: done
created: 2026-11-07 09:27
ask: OK for an ADDITIVE change in steward/models.py (AI-first, decided 09:15)? New models InvestigationStep(finding, record_ids) and Investigation(steps, recommendation, best_asset_id, agrees, why, risks, dropped_steps); StewardResult gets investigation: Investigation | None = None and takeaway: str = ''. Nothing renamed or removed, all defaulted, 279 tests green with it. Used by new steward/investigate.py (LLM reads the evidence dossier, cites ids, advisory only).
files: steward/models.py
reply: seen: used a TEMP line in the same commit (56ee0a1), models.py back to martynas in 646309a
replied: gajus 2026-11-07 09:44
seen_by_sender: yes
