"""Write steward/roster.json: 100 workers, 10 managers, 5 builders (synthetic). Run: python tools/gen_roster.py"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from steward import roster  # noqa: E402

people = roster.generate()
roster.save(people)
print(f"{len(people)} people ->", roster.ROSTER_FILE)
print(Counter(p.role for p in people), Counter((p.plant, p.role) for p in people if p.role != "builder"))
