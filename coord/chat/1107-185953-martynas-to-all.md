id: 1107-185953-martynas-to-all
from: martynas
to: all
kind: done
created: 2026-11-07 18:59
re: 
---
AUDIT DONE (Martynas): docs/audit/martynas.md (0e20c10). Nodes 7, 8, 12, 13 deep, other nodes short, 5 more optimisations + 4 more bold ideas; duplicates of Gajus/Donatas cited and replaced. Headlines: (1) only 4 of 12 governed measures are verified in Desktop: a 12-card check export is ready (C:\SinceAI\pbip_all_measures\unzipped), expected values are in the audit; (2) large pack: startup 46 s because the xlsx is read twice (pandas.read_excel x2 = ~90 s profiled), health 22 s because _more_trusted_duplicate rescans the estate per asset; (3) 69 failed-refresh assets sit on only 14 semantic models, 65 assets on 13 inactive owners: group by root cause; 16 certified assets are on a failed refresh; (4) one request = three spec hashes by role, only the builder's is journaled (provenance, incl. layout_hidden, is outside the hash). Bold idea: the chain as a governed round trip (read a .pbip back, diff its measures against the governed ones). Also: templates/pbip now holds the Desktop-saved card title/subtitle format (e28b4c2), no code uses it yet (build paused).
