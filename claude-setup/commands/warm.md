Prepare the stage demo cache.

1. Check `make ping` works with the live provider.
2. Run `make warm` to record live outputs for demo/inputs.jsonl and the hold-out set into demo/cache/.
3. Verify replay: run the pipeline on demo inputs with DEMO_MODE=1 and confirm every item's source is "cache" (none "rules"). List any that are not.
4. Run `make test`. Remind me to commit demo/cache/.
