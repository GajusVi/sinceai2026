id: 1107-004942-margiris-to-all
from: margiris
to: all
kind: fyi
created: 2026-11-07 00:49
re: 
---
HISTORY REVIEW margiris:
DONE: LLM via backend client 0bc7d83 · unmapped terms force CLARIFY 2a21b77 · 'first sales' guard cc45120 · KPI-id coverage + variant KPIs as conflicts with RULE-002 evidence 9592381 · search reads KPI ids, top-40 window 72cef93 · kpi_index uses MetricDefinition.kpi_id/variants 694242e. 65 tests passed at my last push, 1 xfail (NOT_FEASIBLE).
IN PROGRESS: (a) stopword/phrase fix, 0%, steward/config.py + linking.py; (b) health() under 2 s, 0%, steward/health.py. Not started: L5 NOT_FEASIBLE (steward/decision/engine.py).
KNOWN ISSUES: (1) my T2 rule over-blocks: Power BI, Tableau, workbook, finance, performance, launch, executive, Bayer Pharma land in unmapped_terms, so 9/10 templates CLARIFY (steward/config.py STOPWORDS); my hold-out test only checked metric ids, not unmapped_terms, so it missed this. (2) health() ~45 s on the data pack: steward/health.py:40 _features still uses the old formula path (linking.artifact_metric_ids -> find_terms) for every pair; also finds no duplicates on the data pack. (3) REQ-0001 w/o metadata is EXTEND on AST-0143, EMEA-only though the request says 'global': parser has no market filter. (4) LLM 'unmapped' prompt untested live on the data pack.
NEEDS: Gajus: decision on (3) before the golden is locked; answer to his Tableau-vs-Power-BI question after I check trust.
NOT YET IN NOTES: STOPWORDS contents; AMBIGUOUS_PHRASES (4 phrases); moved untracked demo/cache/987c49eb...json aside (not valid UTF-8; copy in my scratchpad).
