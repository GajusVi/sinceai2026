id: 1108-033336-gajus-to-donatas
from: gajus
to: donatas
kind: done
created: 2026-11-08 03:33
re: 
---
DONE (Gajus, People tab v1, commit 783aa3e, NOT hooked in): steward/roster.py + steward/roster.json (100 workers Worker101-200, 10 managers Manager101-110, 5 builders Builder101-105, plant/role/SUB-ROLE/reports_to, deterministic, synthetic; tools/gen_roster.py), steward/orgmap.py (who sees whom, ticket badges from the shared inbox, manager PROPOSES / builder approves / journaled, overrides on top of the roster), frontend/org_panel.py (cluster map: plant > department > person dots, red ring + flag = open ticket, click or search -> inspector, propose/approve/apply, change log), 14 tests. Seen in Chrome (preview only, night). I added OWNERS line for org_panel.py (like estate_panel). TO HOOK IN (yours, 3 small edits): (1) frontend/steward_app.py TABS: add ('People', 'draft') after Catalog health (managers + builders have 'draft'; workers do not); (2) inside that tab: import org_panel; org_panel.render(user, steward.data_dir, inbox); (3) steward/auth.py: after _ACCOUNTS, add the roster logins: from .roster import accounts; for n, pw, u in accounts(): _ACCOUNTS.setdefault(n, (pw, u)). The 4 demo accounts and the login screen list stay as is. Packaging: build_app must bundle steward/roster.json. Notes: proposals live in the People tab (builder sees them there) not in the main approval queue, to avoid touching inbox.py. UX spec from your design side still welcome (palette, spacing, day theme check not done). Ship OFF unless you say go.
