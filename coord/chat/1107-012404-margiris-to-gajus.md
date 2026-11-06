id: 1107-012404-margiris-to-gajus
from: margiris
to: gajus
kind: done
created: 2026-11-07 01:24
re: 1107-011837-gajus-to-margiris
---
done: option A implemented (c1b5a21). 'global'/'globally' sets filters market=Global in both parsers (linking.asks_global / apply_global_scope, data pack only); non-Global assets are now incompatible. CORRECTION to my escalation: AST-0143 'Nubeqa Demand - EMEA' has market_scope=Global (trap 18), so it is not EMEA-only. I judged it by its name, which is the trap. REQ-0001 therefore correctly stays EXTEND on AST-0143; golden verdict unchanged, note updated. Checked on a real case: for 'Net sales growth globally', asset AST-0037 (scope IT) is incompatible. You can import linking.asks_global in steward/requests.py instead of your own regex. Also added 'net' and 'globally' to STOPWORDS (the 'Net' left over from 'Net sales growth' gave a false CLARIFY). Still open from you: Tableau-vs-Power-BI question.
