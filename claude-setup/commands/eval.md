Run the hold-out evaluation and improve it carefully.

1. Run `make eval`. Report accuracy, macro F1, n, and the sources split (llm/cache/rules).
2. Group misses by cause (label definition, missing context, model error, bad gold label).
3. Propose at most two prompt or label changes with the expected effect. Apply only after I say yes, re-run `make eval`, show before → after.
4. Log the change and result in NOTES.md under Decisions.
