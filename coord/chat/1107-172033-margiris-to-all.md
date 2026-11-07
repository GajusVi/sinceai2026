id: 1107-172033-margiris-to-all
from: margiris
to: all
kind: done
created: 2026-11-07 17:20
re: 
---
DONE dynamic layout, decide side (fe51d63). steward/layout.py + prompts/layout.yaml: the LLM orders the page as a reading sequence (answer -> good or bad -> when it moved -> where from -> what to act on) from specbuild._menu ids only, inside a code-set role envelope (worker 3 cards + trend, management 6 visuals, builder 7). Code validates: unknown/repeated ids dropped, every asked measure and every gap keeps its card, cards first, digits/ids in model text replaced. No LLM or rejected plan = template page for the role (builder unchanged, make demo offline). Steward.build(result, intent, user) takes the viewer. Fills Visual.step/question as soon as spec.py has them (Martynas). Donatas: draw Page.visuals in order. Martynas: semantic.profile can restrict _menu (specbuild._menu is the one place). spec.provenance has layout_source/role/fallback/reason. Live-checked on the backend model. Missing: render tiers by step, UI badge for 'layout by AI'.
