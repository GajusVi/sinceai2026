"""Fill the layout disk cache (steward/layout_cache/) for the demo questions x roles, so the demo replays the AI
layout without a live call or a 429. Live LLM needed (USE_LLM on). Run: make warm-layout. Re-run after a change to
prompts/layout.yaml, the menu (specbuild._menu) or the demo questions. Covers the one-shot path and the "Use
recommended" interview path; a hand-answered interview can still produce a new prompt (then: a live call, cached)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from steward import Steward, layout  # noqa: E402
from steward.auth import login  # noqa: E402

QUESTIONS = [  # frontend/steward_app.py CHIPS + the Bayer REQ-0001 demo request
    "How are we doing in LATAM this quarter?",
    "Is supply safe for Plant-B?",
    "Xarelto net sales in Germany",
    "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country.",
]
USERS = [("Builder12", "Admin123"), ("Manager07", "Manage123"), ("Worker21", "Worker123")]


def main() -> int:
    steward = Steward()
    if steward.llm is None:
        print("No LLM configured (USE_LLM off or no key): nothing to warm.")
        return 1
    ok = miss = 0
    for text in QUESTIONS:
        result = steward.ask(text)
        defaults = steward.interviewer.finish_with_defaults(steward.interviewer.start(text)).intent
        for name, pw in USERS:
            for intent in (None, defaults):
                spec = steward.build(result, intent, login(name, pw)).spec
                if spec is None:
                    continue
                src = spec.provenance.get("layout_source")
                ok += src == "llm"
                miss += src != "llm"
                print(f"{src:8} {name:9} {'interview' if intent else 'one-shot':9} {text[:60]}"
                      + (f"  ({spec.provenance.get('layout_fallback', '')})" if src != "llm" else ""))
    print(f"{ok} layouts cached in {layout.CACHE_DIR}, {miss} fell back (rate limit or rejected: run again).")
    return 0 if not miss else 2


if __name__ == "__main__":
    raise SystemExit(main())
