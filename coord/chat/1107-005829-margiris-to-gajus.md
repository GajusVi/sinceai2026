id: 1107-005829-margiris-to-gajus
from: margiris
to: gajus
kind: fyi
created: 2026-11-07 00:58
re: 1107-004512-gajus-to-margiris
---
done: stopword over-blocking fixed (10cb844). Filler/platform words (Power BI, Tableau, workbook, finance, executive, Bayer Pharma, launch...) no longer land in unmapped_terms. On your 40 hold-out rows 5 templates still CLARIFY on purpose: first sales, performance (x2), launch readiness, supply risk; 'oncology' (brand group) also stays unmapped, so the oncology-brands template CLARIFYs too. Guard test: test_only_genuinely_ambiguous_words_are_unmapped_on_holdout. How to use: pull, nothing to change. Still missing: your Tableau-vs-Power-BI question, answer follows.
