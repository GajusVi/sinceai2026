# LLM providers (checked 5 Nov 2026)

All four go through the same `openai` Python client; only `base_url`, key and model change.
Set in `.env`: `LLM_PROVIDER=<name>` plus that provider's key. `make ping` confirms.

| Provider | base_url | Key | Default model in config.py | Notes |
| --- | --- | --- | --- | --- |
| anthropic | `https://api.anthropic.com/v1/` | `ANTHROPIC_API_KEY` from the Claude Console | `claude-sonnet-5-5` | OpenAI-SDK compatibility layer. Rate limits = standard Messages limits. No prompt caching through this layer; switch to the native `anthropic` SDK (installed) if needed. |
| aitta (CSC / LUMI) | `https://aitta-api.csc.fi/openai/v1` | token from `https://aitta-auth.csc.fi/myToken` | `meta-llama/Llama-3.3-70B-Instruct` | Needs a CSC account with an active LUMI project. Chat completions and embeddings. Pilot service, no availability guarantee: keep a second provider configured. Swagger: `https://api-aitta.csc.fi/docs`. |
| openai | `https://api.openai.com/v1` | `OPENAI_API_KEY` | none: set `LLM_MODEL` | |
| featherless | `https://api.featherless.ai/v1` | `FEATHERLESS_API_KEY` (dashboard → API keys) | none: set `LLM_MODEL`, e.g. `Qwen/Qwen2.5-7B-Instruct`; `make models` lists all | USD 25 Since AI credit. Concurrency limits per plan: check their 'Concurrent Unit Limits' page. |
| gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `GEMINI_API_KEY` from Google AI Studio | none: set `LLM_MODEL`; `make models` lists all | Free tier + student credit. Using it enters MLH 'Best Use of Gemini API' (tick on submission, give project number). Gemini 3 models always reason (can't turn off). |
| ollama | `http://localhost:11434/v1` | none | `llama3.2:3b` | Offline fallback (`./setup_mac.sh --with-ollama`). Slow on an Intel CPU. |

Any other OpenAI-compatible endpoint: `LLM_PROVIDER=custom LLM_BASE_URL=... LLM_API_KEY=... LLM_MODEL=...`.

## Structured output pattern used in backend/llm.py
1. JSON Schema of the Pydantic model goes into the system prompt.
2. Parse the first `{...}` block, validate with Pydantic.
3. On failure, send the error back once and ask for corrected JSON.
4. Cache the validated object in `demo/cache/` (DEMO_MODE replays it).

This avoids provider-specific `response_format` flags, which differ across these four.

Sources: Anthropic OpenAI SDK compatibility docs (platform.claude.com/docs/en/cli-sdks-libraries/libraries/openai-sdk); Aitta docs (aitta.csc.fi/page/docs) and LUMI AI Factory Aitta guide (docs.lumi-supercomputer.eu/laif/inference/aitta/). Offline copies land in docs/vendor/ when setup_mac.sh runs.
