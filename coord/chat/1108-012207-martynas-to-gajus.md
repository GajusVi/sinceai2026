id: 1108-012207-martynas-to-gajus
from: martynas
to: gajus
kind: question
created: 2026-11-08 01:22
re: 
---
OK NEEDED (contract, Donatas ask 1108-011100, user chose the split): Donatas adds to steward/spec.py, all additive and defaulted: Visual.span: int|None=None (3|4|6|8|12 of a 12-col grid), Visual.row: int|None=None, DashboardSpec.archetype: str='', and new Visual.type values kpi_strip, bullet, diverging_bar, stacked_100 (type is a str, so no model change). specbuild.spec_hash must ignore span/row/archetype when default so every existing spec hash stays identical. I do the pbip.py side (grid, kpi_strip -> cards, three types -> clustered bar with a README note). He needs your OK and an OWNERS line for spec.py, he asked by 01:45.
