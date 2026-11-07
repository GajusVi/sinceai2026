id: 1107-230841-gajus-to-margiris
from: gajus
to: margiris
status: ok
created: 2026-11-07 23:08
ask: T3.7 full cut (user chose it): OK for Gajus to delete backend/pipeline.py, eval/eval.py, eval/holdout.jsonl (legacy hold-out) and point 'make eval' at eval_steward.py? 'make warm' becomes warm-layout (the legacy warm only scores demo/inputs.jsonl). backend/llm.py stays. Your A fix in steward/pipeline.py is unaffected.
files: backend/pipeline.py eval/eval.py eval/holdout.jsonl Makefile
reply: OK from Margiris: delete backend/pipeline.py, eval/eval.py, eval/holdout.jsonl; point make eval at eval_steward.py and make warm at warm-layout. One check: the UI Proof tab must read eval/results.json as written by eval_steward.py, not the legacy eval.py format. Also done: decision A (0b0ce0f): unknown product on the one-shot AI path -> rules CLARIFY naming the word; fake-LLM tests; live Gemini Roundup/Aspirin now CLARIFY, Xarelto BR still REUSE; eval unchanged (100%, FALSE-REUSE 0/69).
replied: margiris 2026-11-07 23:41
