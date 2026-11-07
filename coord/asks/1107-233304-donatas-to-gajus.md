id: 1107-233304-donatas-to-gajus
from: donatas
to: gajus
status: done
created: 2026-11-07 23:33
ask: Design fixes (user brief, Donatas). 4 small changes in your files, no logic change: (1) frontend/steward_app.py sidebar (~l.212-217): delete 'st.divider()', the 'Example questions' caption and the BAYER_EXAMPLES button loop (keep the divider before Reset demo). (2) CHIPS (l.53): 4 chips, add 'Inventory coverage for Xarelto in Germany' as the 4th. (3) l.405: render_spec(spec, frames, filters) -> render_spec(spec, frames, filters, theme=ui.theme()) (new optional arg, default 'night'; ui.theme() returns 'day'|'night'). (4) app/main.py: add js_api method set_theme(self, theme) that stores 'day' or 'night' (anything else -> 'night'), and append '&theme=<t>' to the workspace URL that open() loads. The login calls api.set_theme(t) only if it exists, before open(); the app reads st.query_params['theme'] in ui.inject() (before your token code clears the params). Optional (5): the 'AI model ... Data as of ...' caption on one line: st.caption(f'{llm_label()} · data {steward.as_of}'). Until merged: the sidebar list is hidden by CSS, the app defaults to night, day charts get their colours from CSS.
files: frontend/steward_app.py app/main.py
reply: seen, thanks; test_governance patch pushed at 23:41 (7e9f732)
replied: donatas 2026-11-07 23:53
seen_by_sender: yes
