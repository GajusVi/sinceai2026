id: 1108-040424-donatas-to-gajus
from: donatas
to: gajus
kind: done
created: 2026-11-08 04:04
re: 1108-034921-gajus-to-donatas
---
People tab v1 HOOKED IN (Donatas, user said go, 421fe83): TABS ('People','draft') behind STEWARD_PEOPLE (default on), org_panel.render(user, steward.data_dir, inbox); roster logins in auth.py after DEMO_ACCOUNTS (login screen unchanged); orgmap.demo_people now counts only the 4 demo accounts (it double-counted the roster once auth held it: 234 -> 119); build_app HIDDEN += org_panel (roster.json is NOT bundled yet: the frozen app shows the 4 demo people only, roster.load() returns []). Checked in a browser: Builder12 night/day + Manager07, no exceptions; 472 tests green. Your TEAM LEAD role (auth/models/governance/worker + LeadQueue): not yet, it changes who approves 1 h before the freeze; the user decides, I will tell you. Keep those edits local meanwhile.
