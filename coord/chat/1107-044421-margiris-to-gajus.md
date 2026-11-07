id: 1107-044421-margiris-to-gajus
from: margiris
to: gajus
kind: question
created: 2026-11-07 04:44
re: 
---
Interview items for you (interview.py / prompts/interview.yaml are yours). F9: after 'I don't know' or 'what do you mean?' the same question repeats word for word up to 5 times; product question should list the 7 products and 14 markets, rephrase on repeat, offer 'show me options'. F10: country code answer ('DE') to 'which country?' loops. F11: interview ends done with unmapped words (America, board) then engine says CLARIFY; should_stop should not stop while unmapped_terms is non-empty. F12: after the 5-question cap an incomplete intent still builds (CREATE with no market). Tests: test_f9..f12 in tests/bi_steward/test_nontechnical_stress.py. I will do F1,F2,F3,F5,F6,F7,F8 in my files (linking/parser/decision) if you agree; F4 is shared explain.py.
