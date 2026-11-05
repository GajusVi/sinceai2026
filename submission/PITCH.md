# Finals: 4 minutes + up to 6 minutes Q&A (one question per judge)

## Script
| Time | Beat | Line (fill in) |
| --- | --- | --- |
| 0:00-0:30 | Hook: user + pain | "[Role] at [company] handles [N] [items] a week by hand. One wrong call costs [x]." |
| 0:30-2:15 | Live demo, core flow | Upload → queue sorted by priority → open one → evidence → approve → export. Run `make demo`. |
| 2:15-2:45 | Proof | "On [n] held-out examples we got [accuracy]. Here are the misses." |
| 2:45-3:20 | Euro impact | Show the formula on screen, not only the total. |
| 3:20-4:00 | Pilot | "4-week pilot: week 1 connect [system], weeks 2-3 shadow mode, week 4 measure against [metric]." |

## Prepared answers
**Investor:** who pays, how much, how big, why us
- Buyer: [ ] · price: [ ] · market: [ ] · why us: [ ]

**Startup ecosystem:** what is the pilot, who signs it
- Pilot owner at the company: [role] · success metric: [ ]

**Software-engineering professor (AI agents):** how did you verify the AI, what fails, what is logged
- Hold-out set labelled before tuning; we report misses, not only accuracy.
- Every output is schema-validated; invalid JSON gets one repair, then falls back to rules, marked in the UI.
- Audit log: input, model output, source, human verdict, timestamp. Exportable CSV.
- Known failure: [ ].
