id: 1107-052741-margiris-to-gajus
from: margiris
to: gajus
kind: done
created: 2026-11-07 05:27
re: 
---
F1-F8 + the off-topic clarify are pushed (017c73a): 269 tests green, all 19 stress xfails gone. interview.yaml has fallback.clarify and the clarify rule: please take it back in OWNERS. Changes you may notice: explain.py CLARIFY text names the unknown word and shows 'did you mean'; answers drop from ~11k to ~500 chars (conflicts only for the recommended assets, no KPI ids); query_parser: several named values of one dimension become a breakdown (intent_from_parsed still keeps only a single filter value, so the one-shot dashboard for 'Xarelto vs Eylea' shows all products; your file, not changed); pipeline.py gets a small _horizon_note (period outside Jan-Oct 2026 -> DATA warning). Still open for me, as you asked: conversation tests against the real LLM; no Aitta key on this machine and Gemini returns 429, so I need a key or your run.
