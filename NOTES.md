# NOTES: who does what, decisions, open questions

## Team
| Who | Role | Owns |
| --- | --- | --- |
| Gajus | product + finance story | challenge pick, euro case, pitch, submission page |
| Quant econ teammate | model + eval | hold-out labels, eval.py, metric |
| Medical teammate (radiology) | domain + data | company Q&A, data cleaning, edge cases |
| Data analyst / law teammate | data + rules | data analysis, NDA/IP/data rules, claims checking |

## Challenge ranking (rev. Thu 5 Nov 23:25, LLM council round 2: Opus/Sonnet/Haiku; no domain expertise; keep IP)
Select in this order: 1. Bayer  2. Lindstrom  3. Fonecta  4. Europress
Take Lindstrom first if Bayer looks full or crowded at selection.
Then: 5. FORCIT  6. Meyer Turku  7. Elisa  8. Apetit  9. Turku Energia  10. Business Turku  11. Valmet  12. Traficom  13. TrustED
Excluded (IP goes to company): Takomo Golf, DNA

## One-sentence demo (Fri 21:30 latest)
For [user], takes [input], returns [output], so they can [benefit].

## Decisions
- 2026-11-05: scaffold = FastAPI + Streamlit + SQLite audit log; LLM via OpenAI-compatible client (provider by env).

## Questions for the company (Sat 09:00-12:00 Q&A)
-

## Cut list (Sat 12:00 checkpoint)
-
