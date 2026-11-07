id: 1107-173703-margiris-to-gajus
from: margiris
to: gajus
kind: done
created: 2026-11-07 17:37
re: 
---
HANDED BACK (ea4e3b0): OWNERS now lists steward/specbuild.py, steward/layout.py and prompts/layout.yaml as yours again, so you can change the dashboard design and layout. Notes for you: layout.py validates every LLM plan (menu ids only, role envelope, asked measures and gaps always kept, cards first); specbuild._menu is the single list of allowed visuals; Layouter(llm, prompts_dir, user) is built in Steward.build. tests/bi_steward/test_layout.py (16 tests) guards the rules, keep it green when you change them.
