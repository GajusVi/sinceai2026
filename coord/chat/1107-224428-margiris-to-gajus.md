id: 1107-224428-margiris-to-gajus
from: margiris
to: gajus
kind: question
created: 2026-11-07 22:44
re: 
---
ESCALATE (Margiris): live LLM run on Gemini 17/18 (4e18170). Red: one-shot 'Roundup sales in Brazil' -> EXTEND AST-0019 (All Pharma Forecast). Cause is code, not the model: Steward._ask_ai runs an expert interview that closes at once; Interviewer._close (steward/interview.py:359) moves the unknown product word to ignored_terms, products stay empty = All Pharma, so a foreign product builds. 'Aspirin in Germany' same path (passed only because it landed on CREATE). Rules path gives CLARIFY for both. Options: A) in _ask_ai (steward/pipeline.py), if the intent ignored a word and has no product or site, return None so the rules parser answers (CLARIFY naming the word); ~3 lines + fake-LLM test, no golden change expected. B) leave it; the packaged app runs LLM off so stage is safe, the live UI is not. I recommend A because the live app on Gemini is the AI-first path judges will try. OK to do A?
