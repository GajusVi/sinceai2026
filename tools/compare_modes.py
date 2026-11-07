"""AI-first vs rules: all 150 Business_Requests through Steward.ask + build, once with the LLM and once without.

Numbers come from code only (BUILD_PLAN: never typed by hand). Output: docs/steward/compare_modes.json + a summary line.
Usage: STEWARD_CATALOG=datapack .venv/bin/python tools/compare_modes.py [--limit N] [--workers 6]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("STEWARD_CATALOG", "datapack")

from steward import Steward  # noqa: E402
from steward.config import Settings  # noqa: E402
from steward.requests import load_requests  # noqa: E402

OUT = ROOT / "docs" / "steward" / "compare_modes.json"
_local = threading.local()


def steward(use_llm: str) -> Steward:
    key = f"s_{use_llm}"
    if not hasattr(_local, key):  # one Steward per thread: the interviewer keeps per-call state
        settings = replace(Settings.from_env(), use_llm=use_llm, as_of=date(2026, 11, 6))
        setattr(_local, key, Steward(settings=settings, data_dir=ROOT / "data" / "steward" / "compare"))
    return getattr(_local, key)


def run_one(req, use_llm: str) -> dict:
    t = time.time()
    try:
        s = steward(use_llm)
        r = s.build(s.ask(req.text, req.context))
    except Exception as e:  # a crash is a result too
        return {"id": req.request_id, "error": str(e)[:200]}
    inv = r.investigation
    return {
        "id": req.request_id,
        "verdict": r.decision.verdict.value,
        "best": r.decision.best.artifact.id if r.decision.best else "",
        "parser": r.question.parser,
        "spec": r.spec.change_type if r.spec else "",
        "lint_block": bool(r.spec and any(x.status == "block" for x in r.spec.lint)),
        "ai_recommendation": inv.recommendation if inv else "",
        "ai_asset": inv.best_asset_id if inv else "",
        "ai_agrees": inv.agrees if inv else None,
        "ai_steps": len(inv.steps) if inv else 0,
        "ai_dropped": inv.dropped_steps if inv else 0,
        "seconds": round(time.time() - t, 1),
    }


def summary(rows: list[dict]) -> dict:
    ok = [r for r in rows if "verdict" in r]
    n = len(rows)
    verdicts = Counter(r["verdict"] for r in ok)
    no_new = sum(v for k, v in verdicts.items() if k in ("REUSE", "EXTEND", "CONSOLIDATE"))
    inv = [r for r in ok if r["ai_steps"]]
    return {
        "requests": n,
        "errors": n - len(ok),
        "verdicts": dict(verdicts),
        "built_a_spec": sum(1 for r in ok if r["spec"]),
        "clarify_rate": round(verdicts.get("CLARIFY", 0) / n, 3) if n else 0,
        "without_a_new_dashboard": round(no_new / n, 3) if n else 0,
        "ai_trails": len(inv),
        "ai_disagreements": sum(1 for r in inv if r["ai_agrees"] is False),
        "ai_dropped_steps": sum(r["ai_dropped"] for r in inv),
        "median_seconds": sorted(r["seconds"] for r in ok)[len(ok) // 2] if ok else 0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    reqs = load_requests()[: args.limit or None]
    result = {}
    for mode, workers in (("off", 1), ("auto", args.workers)):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(pool.map(lambda r, m=mode: run_one(r, m), reqs))
        result["rules" if mode == "off" else "ai"] = {"summary": summary(rows), "rows": rows}
        print(mode, json.dumps(summary(rows)), flush=True)
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
