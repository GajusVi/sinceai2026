Pre-submission check (target Sun 08:00, hard deadline 10:00 in sinceai.app). Report PASS/FAIL for each:

1. `make test` passes; DEMO_MODE=1 path works with no network (all demo items from cache).
2. README runs in under 5 minutes from a fresh clone.
3. No secrets in git: .env untracked; `git grep -nE "sk-[A-Za-z0-9]{10,}"` finds nothing.
4. No confidential challenge data in tracked files, screenshots or the video (FORCIT rules if relevant).
5. submission/SUBMISSION.md complete: title with the number, decision-screen screenshot first, ~2 min captioned video, proof numbers matching eval/results.json, euro formula, one honest limitation.
6. submission/AI_TOOLS.md lists the tools; pre-event work tagged `pre-event`.
7. Optional award ticks decided (Gemini project number, Red Hat/FIWARE evidence) and noted in NOTES.md.
Then list what is left, most important first.
