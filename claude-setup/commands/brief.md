We just got the full challenge brief. Turn it into a working first version of the app.

Input: $ARGUMENTS (path to the brief/materials in the repo, or pasted text).

1. Extract: the named user, what they do today, the input data and format, the decision/output they need, the metric the company cares about, and every data/NDA/IP rule. Ask me only about blockers.
2. Write the one-sentence demo ("For [user], takes [input], returns [output], so they can [benefit]") and add it plus the extracted facts to NOTES.md.
3. Edit in this order, small diffs: backend/pipeline.py (LABELS, URGENT, prompt) · backend/models.py (rename Item, add only fields the UI shows) · .env.example USER_ROLE · frontend/app.py TITLE/TAGLINE · demo/inputs.jsonl (5-10 real or approved examples: one wow, one messy, one edge case) · eval/holdout.jsonl skeleton.
4. Never copy confidential data into tracked files unless the rules allow it.
5. Run `make test` and report.
