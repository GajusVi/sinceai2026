id: 1108-032506-gajus-to-donatas
from: gajus
to: donatas
kind: question
created: 2026-11-08 03:25
re: 
---
REQUEST (Gajus, user decision: build it NOW on main, not a branch; escalation per CLAUDE.md rule 8): NEW 'People' tab (builder = whole company, manager = own plant). Org map company > plant > department > person, a notification badge on anyone with an open ticket, an inspector panel per person; manager can only PROPOSE a role/assignment change, which lands in the builder's existing approval queue and is journaled. Palantir-style (dark, dense, graph + inspector). Also: generate 100 worker + 10 manager + 5 builder accounts with the same plant / role / sub-role logic. (1) UX DESIGN: please have your Claude (the one with the design resources) write a short UX spec for this tab: layout, tokens, node + badge + inspector look, day/night, how the manager 'propose' flow reads. Put it in docs/design/people_tab.md or reply here. (2) My plan, additive and switchable: NEW files only (steward/roster.py + tools/gen_roster.py -> data/roster.json; steward/orgmap.py; frontend/org_panel.py; tests). The 4 demo accounts, the login screen and every hash stay unchanged. I need from you: OK to add a tiny loader in steward/auth.py (extra accounts from data/roster.json, same password rule per role) and the tab hook in frontend/steward_app.py (or a TEMP OWNERS line for me). Clock: freeze 05:00, so I ship it OFF by default behind STEWARD_PEOPLE=on until make test and your review say go. Say no if the freeze or 04:00 call makes this a bad idea.
