# 04 Google Dev workshops (Jason Mayes, Google Web AI), Fri 6 Nov

Two talks: keynote "Web AI / agentic web" and the Antigravity build demo. Relevance to the Bayer build is moderate:
the **method** transfers directly; the client-side tech is optional garnish.

## Method for building with agents (transfers to Claude Code too)
1. State scope up front (which folder/files), saves tokens and wrong edits.
2. Write coding rules once as if onboarding a junior (his: vanilla JS, no frameworks without asking, Google style guide,
   functions <= 30 lines, split into modules). Put reusable rules in the global rules file (Antigravity GEMINI.md == our CLAUDE.md).
3. **Start from a boilerplate you can already explain**, pre-download models/assets to avoid auth loops.
4. Explain the code's flow, give the first task with **doc URLs** so the agent doesn't rely on training data.
5. Use planning mode, review/comment the plan like a design doc, then proceed.
6. Small incremental prompts, each one breaking the feature into 2-4 explicit steps with your design choices
   (e.g. chunk by paragraph, cosine sim via TF.js, colour scale). Cheap model (Flash) for simple steps, Pro for hard ones.
7. Paste console warnings / screenshots back for fixes. Refactor into modules at the end. Final manual review pass.
Claimed result: ~10x faster than hand coding.

His 7 prompts (Prompts/1-7) build: tokenizer + EmbeddingGemma (LiteRT.js) -> token/embedding visualiser ->
cosine similarity of 2 texts (TF.js WebGPU) -> async fix -> **client-side vector DB on IndexedDB, paragraph chunking, top-3 search**
-> refactor (tokenizer.js, embeddingModel.js, cosineSimilarity.js) -> UI fix.

## Tech mentioned
- Gemma 3/4 run in-browser (LiteRT-LM.js); EmbeddingGemma-300m for embeddings; his VectorSearch.js library (GPU vector DB);
  caching proxy for big models; Kokoro TTS, Whisper WebGPU, etc.
- **WebMCP**: W3C draft; site exposes existing functions as agent tools (declarative in HTML forms or imperative JS),
  site stays in control, can require human confirmation for sensitive actions.
- Agent = LLM(s) + memory + tools + orchestration loop.

## What we could actually use
- **Embedding similarity for duplicate detection / reuse search** over asset names + KPI sets + descriptions: exactly the
  vector-search pattern he built. Can run server-side (any embedding API) or client-side (EmbeddingGemma) for a "no data leaves the browser" governance story.
- **MLH "Best use of Gemini API"** is an optional prize tick on the same submission (event-facts): if one step
  (e.g. grill-me or explore) runs on Gemini, we qualify. Students get Google AI Pro + AI Studio credits.
- His "human confirmation for sensitive actions" in WebMCP = same principle as our approve/reject gate.
