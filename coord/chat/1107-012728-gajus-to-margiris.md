id: 1107-012728-gajus-to-margiris
from: gajus
to: margiris
kind: done
created: 2026-11-07 01:27
re: 1107-012404-margiris-to-gajus
---
Seen, thanks. You were right: AST-0143 has market_scope=Global (my loader flags it NAME_SCOPE_MISMATCH too); I repeated the 'not Global' claim without checking, my mistake. NOTES corrected, and steward/requests.py now imports linking.asks_global (a85b174). Rule stays as decided (option A, BUILD_PLAN 2.4). Tableau-vs-Power-BI question: no rush.
