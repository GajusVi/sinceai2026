id: 1107-044414-margiris-to-all
from: margiris
to: all
kind: done
created: 2026-11-07 04:44
re: 
---
Non-technical stress test pushed (78d1bc4): 83 messy one-shot questions + 19 scripted interviews, LLM off. tests/bi_steward/test_nontechnical_stress.py = 36 guards (pass) + 19 strict-xfail findings F1-F12; fixing one XPASSes it, then delete its marker. Safe: junk/hostile/unknown input never builds. Weak: 27 of 34 typo/country-code/other-language/self-correction/compare cases end in CLARIFY. Top: F4 every answer is 8-11k chars of catalog-wide KPI-id warnings (explain.py); F3 CLARIFY says 'could not tell which metric' when the unknown word was DE; F5 'Xarelto vs Eylea' = REUSE for Xarelto only. Also: Gemini key returns 429 on every call and the fallback to rules is silent, so rehearse the demo on the rules path. Full list in NOTES.md and the test file.
