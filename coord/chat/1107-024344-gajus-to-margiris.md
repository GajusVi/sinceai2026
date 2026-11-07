id: 1107-024344-gajus-to-margiris
from: gajus
to: margiris
kind: need
created: 2026-11-07 02:43
re: 
---
Small one for your STOPWORDS (steward/config.py), no rush: the rules fallback of the interview still sees filler words 'actually', 'just', 'good' as unmapped (e.g. 'Actually just net sales for Kerendia worldwide' -> unmapped Actually, just), which would force CLARIFY. FYI Gemini returned 429 rate-limit during my real-model run; the fallback carried the interview, so the demo needs warmed conversations (Donatas, make warm) and the rules path as backup.
