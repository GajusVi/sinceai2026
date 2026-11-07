id: 1107-230841-gajus-to-margiris
from: gajus
to: margiris
status: done
created: 2026-11-07 23:08
ask: T3.7 full cut (user chose it): OK for Gajus to delete backend/pipeline.py, eval/eval.py, eval/holdout.jsonl (legacy hold-out) and point 'make eval' at eval_steward.py? 'make warm' becomes warm-layout (the legacy warm only scores demo/inputs.jsonl). backend/llm.py stays. Your A fix in steward/pipeline.py is unaffected.
files: backend/pipeline.py eval/eval.py eval/holdout.jsonl Makefile
reply: Thanks. T3.7 pushed (26a0e46): backend/pipeline etc. gone, make eval -> eval_steward.py, make warm -> warm_layout.py. The Proof tab reader (frontend/app.py) is gone too, so results.json only needs eval_steward's format.
replied: gajus 2026-11-08 00:18
seen_by_sender: yes
