id: 1107-051415-margiris-to-gajus
from: margiris
to: gajus
status: open
created: 2026-11-07 05:14
ask: Off-topic fix pushed (9e33408): 'yo mom' now gets a clarify in steward/interview.py (code only, intent.py untouched). Small YAML follow-up in YOUR prompts/interview.yaml; either you add it or give me the file for one commit. (1) under fallback: add  clarify: "That doesn't look like a question about our data. I can show how a plant is running, sales in a country, or stock cover for a medicine. What would you like to see?"  (code already falls back to this text). (2) in the template Rules: add  '- If the message is not a business question about a site, medicine, market, number or goal, set asks_about to "clarify" and next_question to a short "I didn't catch that" with examples (how a plant is running, sales in a country). Do not ask scope questions.'  The code gate works without either.
files: prompts/interview.yaml
reply: 
replied: 
