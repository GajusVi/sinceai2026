# [Product name]: [one line with the number, e.g. "routes 92% of tickets correctly, saves 4 min each"]

![decision screen](screenshot-queue.png)  <!-- first image = the decision screen, not a landing page -->

**Video (~2 min, English, captions, screen not slides):** [link]  problem → user action → AI action → result → value. Label anything mocked.

## The user and the problem
[Named role] at [company] spends [time] on [task]. Wrong calls cost [x].

## What it does
1. Ingests [company data] into typed records.
2. Scores each one with a label, priority, confidence, reason and quoted evidence.
3. Shows a queue: approve or reject, export approved items.
4. Logs every model output and human decision (audit trail).

## Proof
- Hold-out: n = [ ], accuracy [ ], macro F1 [ ]. Misses listed in the app.
- Timed task: [before] min → [after] min on [realistic task].
- Euro impact: [items/month] × 12 × [min saved] ÷ 60 × €[rate]/h = **€[ ]/year**.
- Limitation: [one honest sentence].

## Run it (under 5 minutes)
```
./setup_mac.sh          # or: uv venv && uv pip install -r requirements.in
make demo               # no API key needed: replays cached outputs
make ui                 # live, needs a key in .env
```

## AI tools and prior work
See AI_TOOLS.md. Pre-event scaffold is tagged `pre-event`; everything after it was built during the event.
