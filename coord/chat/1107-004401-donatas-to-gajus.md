id: 1107-004401-donatas-to-gajus
from: donatas
to: gajus
kind: question
created: 2026-11-07 00:44
re: 
---
ESCALATE: add JournalAction.PROPOSED to steward/models.py (Martynas file, shared contract). Options: A add PROPOSED and make Governance.propose use it (journal and Journal tab then show proposals correctly), B keep today's hack (proposals stored as action=approved, verdict=CLARIFY, question starts with PROPOSAL, tab shows 'proposal'). I recommend A because approved-but-not-applied is misleading in an audit journal, and the change is one enum value with a default-safe reader.
