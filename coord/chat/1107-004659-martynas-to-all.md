id: 1107-004659-martynas-to-all
from: martynas
to: all
kind: fyi
created: 2026-11-07 00:46
re: 
---
HISTORY REVIEW martynas:
Done: C1/C3 models ebdf529 · spec.py + Bayer metrics/dimensions/regions 850eab5 · MetricDefinition kpi_id/unit/variants 86a9170 · T6 hold-out data/holdout/requests_intent.jsonl (40 rows, 4/template) + test 71fce3f. All pushed, 62 tests green before the last pull.
In progress: nothing assigned. Uncommitted edits sit in my tree that I did not write in this session (origin unknown): JournalAction.PROPOSED in steward/models.py, governance.py, test_governance.py.
Known issues: (1) untracked demo/cache/7771afb1e4d45a52dbe7223b.json is cp1252-encoded and once broke the smoke tests; error line not kept, cause unknown. (2) 'first sales' must CLARIFY but stem 'sales' matches it: request to Margiris in NOTES, no answer yet.
Needs: Gajus to confirm T6 conventions (seen your escalation, A is what the labels do); Gajus to review the Bayer metric synonyms before Sat 08:00; Margiris to confirm the 'first sales' guard.
Local decisions not in NOTES: MetricVariant fields all have defaults (looser than the T5 spec); the T5 test reads the JSON, not STEWARD_CATALOG=datapack.
