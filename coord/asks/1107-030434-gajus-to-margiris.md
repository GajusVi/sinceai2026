id: 1107-030434-gajus-to-margiris
from: gajus
to: margiris
status: done
created: 2026-11-07 03:04
ask: Need a second LLM fallback in backend/llm.py: new .env setting LLM_FALLBACK_PROVIDER (e.g. gemini). If the primary provider (aitta) raises in complete_json or in BackendClient.generate_text (network, 429, 5xx, timeout), retry the same call once on the fallback provider before raising, so the chain is aitta -> gemini -> rules. Keep the cache key the same and log which provider answered. One test with a fake failing primary. Small, by 12:00 if possible.
files: backend/llm.py steward/llm.py
reply: Done in b9d1f79 (744cb67 + test fix): LLM_FALLBACK_PROVIDER read inside backend/llm.py, so backend/config.py is untouched. Transport failures of complete_json and BackendClient.generate_text (now backend.llm.chat_text) retry once on the fallback; invalid JSON does not; cache key unchanged; log line says which provider answered. 7 tests with a fake failing primary. To use: add LLM_FALLBACK_PROVIDER=gemini to .env (documented in .env.example).
replied: margiris 2026-11-07 04:09
