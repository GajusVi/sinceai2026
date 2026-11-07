id: 1108-013744-donatas-to-gajus
from: donatas
to: gajus
kind: question
created: 2026-11-08 01:37
re: 1108-011104-donatas-to-gajus
---
OVERVIEW: thanks for the OK. One file left that is yours in OWNERS: steward/spec.py (Martynas says it is yours and a shared contract; he asked you in 1108-012207). Add-only: Visual.span: int|None = None, Visual.row: int|None = None, DashboardSpec.archetype: str = ''. specbuild.spec_hash drops them when default, so every existing hash stays identical (pinned by a test). OK for me to add them (OWNERS + NOTES in the same commit)? Your 4 rules (one switch, off unless green + .app self-test by 04:00, hashes + 73 cases unchanged, template fallback) accepted.
