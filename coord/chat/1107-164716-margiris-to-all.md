id: 1107-164716-margiris-to-all
from: margiris
to: all
kind: question
created: 2026-11-07 16:47
re: 
---
PROPOSAL dynamic dashboard, decide side (Margiris). WHO DECIDES: code sets the envelope per role (worker = answer+status of own plant, manager = full story own plant, builder = full story + governance); the LLM orders the reading sequence inside it and picks the visual per step from a fixed menu (card/line/bar/table/gap) plus comparison+threshold from menus. Verdict, numbers, gaps stay code; a gap is always forced in as a labelled gap card. CONTRACT: hierarchy = reading order, each step answers the next question (the answer -> good or bad? -> when did it move? -> where from? -> what to act on -> detail). New steward/layout.py: propose(ctx)->LayoutPlan, validate(plan,ctx) (ids exist, menu-only, no digits in text, lint FOCUS, role envelope); any failure or no LLM -> today deterministic template, so make demo works offline. Visual gets additive fields step:int and question:str. FILES: mine = steward/layout.py, prompts/layout.yaml, tests/bi_steward/test_layout.py. DIBS = specbuild.py (only the _page hook, calls layout.plan). ASK Martynas: Visual.step + Visual.question in spec.py (additive, defaulted). ASK Donatas: render.py draws in step order. TESTS: stub LLM (valid/garbage/out-of-menu) -> fallback; 3 golden cases unchanged offline; worker/manager/builder keep the same numbers and gaps; one live check, I have a working key. Martynas: your angle = data shape in the context + PBIP/render use of step; shout if you want it split differently.
