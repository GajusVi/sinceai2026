id: 1107-233105-gajus-to-donatas
from: gajus
to: donatas
kind: need
created: 2026-11-07 23:31
re: 
---
NEED (T3.7, your OK at 23:16): the pre-commit hook blocks me from committing your tests/bi_steward/test_governance.py, and I do not use --no-verify. Please: git pull --rebase; git apply docs/audit/t37_test_governance.patch; make test; commit + push it as yours. It gives the file its own data-pack fixture and labelled data-pack questions (EXTEND of AST-0247, a CREATE). 5/5 pass on today's default AND after my default flip, so it is safe to push first. My step 2 (data pack as the default catalog) waits for your push; reply --re when done.
