id: 1107-044553-margiris-to-gajus
from: margiris
to: gajus
status: open
created: 2026-11-07 04:45
ask: Margiris wants to fix the stress-test findings (F1-F12, tests/bi_steward/test_nontechnical_stress.py, commit 78d1bc4) himself instead of handing them over. Requesting your OK to edit these files of yours, small commits, make test green each time, each fix deletes its xfail marker: (1) steward/intent.py: Intent.should_stop stays False while unmapped_terms is non-empty, and no build after the 5-question cap with an incomplete intent (F11, F12; contract change, so your call). (2) prompts/interview.yaml: fallback questions list the 7 products and 14 markets, rephrase on repeat, 'show me options' path (F9). (3) steward/interview.py: country-code answers, non-answers like 'I don't know' are not unmapped terms, 'I mean/actually' replaces the earlier value (F6, F9, F10). (4) steward/explain.py: CLARIFY names the unknown word, conflict warnings limited to the recommended/alternative assets, max 3 shown (F3, F4). (5) data/build_bayer_dictionaries.py + catalog/bayer/dimensions.json (Martynas's): add brasil/usa/america synonyms (F1). My own files (linking, query_parser, decision) need no OK. Reply ok or no per item; if no, I leave that item to you.
files: steward/intent.py prompts/interview.yaml steward/interview.py steward/explain.py data/build_bayer_dictionaries.py catalog/bayer/dimensions.json
reply: 
replied: 
