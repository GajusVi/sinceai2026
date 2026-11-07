id: 1107-030434-gajus-to-margiris
from: gajus
to: margiris
status: open
created: 2026-11-07 03:04
ask: Need a second LLM fallback in backend/llm.py: new .env setting LLM_FALLBACK_PROVIDER (e.g. gemini). If the primary provider (aitta) raises in complete_json or in BackendClient.generate_text (network, 429, 5xx, timeout), retry the same call once on the fallback provider before raising, so the chain is aitta -> gemini -> rules. Keep the cache key the same and log which provider answered. One test with a fake failing primary. Small, by 12:00 if possible.
files: backend/llm.py steward/llm.py
reply: 
replied: 
