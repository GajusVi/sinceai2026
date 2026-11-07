id: 1107-092758-gajus-to-martynas
from: gajus
to: martynas
status: open
created: 2026-11-07 09:27
ask: OK for an ADDITIVE change in steward/models.py (AI-first, decided 09:15)? New models InvestigationStep(finding, record_ids) and Investigation(steps, recommendation, best_asset_id, agrees, why, risks, dropped_steps); StewardResult gets investigation: Investigation | None = None and takeaway: str = ''. Nothing renamed or removed, all defaulted, 279 tests green with it. Used by new steward/investigate.py (LLM reads the evidence dossier, cites ids, advisory only).
files: steward/models.py
reply: 
replied: 
