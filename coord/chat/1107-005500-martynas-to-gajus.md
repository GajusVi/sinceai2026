id: 1107-005500-martynas-to-gajus
from: martynas
to: gajus
kind: done
created: 2026-11-07 00:55
re: 1107-005227-gajus-to-martynas
---
T6 option C done, b4fe61d on main: metadata_severity on all 40 rows (blocker 14, confirm 5, none 21), same 40 ids. confirm = REQ-0002, 0010, 0028, 0040, 0049; none = REQ-0038 (I also set its metadata_conflict to false and dropped the country-level-vs-region rule from data/build_holdout_intent.py). REQ-0016/0019 stay none. 77 passed, 1 xfailed with your test now reading my labels.
