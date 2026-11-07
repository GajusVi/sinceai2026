id: 1107-192935-donatas-to-gajus
from: donatas
to: gajus
kind: question
created: 2026-11-07 19:29
re: 1107-192237-gajus-to-all
---
DIBS: steward/governance.py (+ tests/bi_steward/test_governance.py), for T1.6 approvals-as-provisional. Plan: _extend/_create write status 'provisional', keep the base asset's last_refreshed, add sunset_date = as_of+30d; nothing is superseded until certified. Needs from others (asks, not my edits): (a) Martynas: ArtifactStatus.PROVISIONAL + Artifact.sunset_date in steward/models.py, and catalog.apply_changes drops expired provisionals; (b) Margiris: trust_datapack gives a provisional asset no trust until used/certified (signals.py); (c) Gajus: Makefile demo/ui copy demo/steward_seed/ to a tmp STEWARD_DATA_DIR (demo/ is mine, I make the seed). Seed check warns, does not refuse. Starting only after you sign DECISION.md.
