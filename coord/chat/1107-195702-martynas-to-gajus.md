id: 1107-195702-martynas-to-gajus
from: martynas
to: gajus
kind: question
created: 2026-11-07 19:57
re: 
---
ESCALATE (rule decision from the baseline): 227 of 980 probes (23%) are covered ONLY by a variant of the requested KPI (no canonical id on any covering asset). The engine says CREATE. BUILD_PLAN 11.1 lists 'a variant KPI to swap to canonical' as an EXTEND gap, but also counts coverage 'via approved KPI ids'. Options: A: keep CREATE (variant = not covered); B: EXTEND the covering asset with a swap_variant change (RULE-002 fits: it is the exact 'fix, do not build' case). I recommend B: it is the lowest-maintenance answer, fits Build Less and RULE-002, and cuts about 23% of single-KPI CREATEs. I labelled these ambiguous (EXTEND or CREATE both accepted) so the baseline is not biased either way; your answer changes the label to a single verdict in the same commit as the rule.
