"""Backtest the engine on real requests (Gajus, Sun 8 Nov): replay the autofill log (steward/suggest.py requests.jsonl)
through today's code and list every request whose verdict or chosen report changed.

    .venv/bin/python tools/backtest_requests.py                 # the memory dir (STEWARD_MEMORY_DIR or app data)
    .venv/bin/python tools/backtest_requests.py --log path.jsonl --json out.json

A logged Intent is replayed as it was confirmed (ask_intent: same request, same answer expected); a row without one
(expert mode, an interview that ended before an Intent) is replayed from its text. Rules only, no LLM, no writes.
Refused rows (another plant) are a permission outcome, not a decision: they are skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path
from tempfile import mkdtemp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    from steward import Steward
    from steward.config import Settings
    from steward.intent import Intent
    from steward.suggest import LOG, Suggestions, memory_dir

    ap = argparse.ArgumentParser()
    ap.add_argument("--log", type=Path, default=memory_dir() / LOG)
    ap.add_argument("--json", type=Path, default=None, help="write the per-row results here")
    args = ap.parse_args()

    rows = [r for r in Suggestions(args.log.parent).history() if r.get("verdict") != "REFUSED"]
    if not rows:
        print(f"No requests logged in {args.log}. Ask a few questions in the app first.")
        return
    os.environ.setdefault("STEWARD_USE_LLM", "off")
    settings = replace(Settings.from_env(), use_llm="off", data_dir=Path(mkdtemp()), as_of=date(2026, 11, 6))
    steward = Steward(settings=settings)

    out, changes = [], Counter()
    for r in rows:
        try:
            if r.get("intent"):
                res = steward.ask_intent(Intent(**r["intent"]), explain=False)
            else:
                res = steward.ask(r["text"])
            now = {
                "verdict": res.decision.verdict.value,
                "asset": res.decision.best.artifact.id if res.decision.best else None,
            }
        except Exception as e:  # noqa: BLE001 - a crash is a finding, not an abort
            now = {"verdict": "ERROR", "asset": None, "error": str(e)[:160]}
        same = now["verdict"] == r["verdict"] and (now["asset"] == r.get("asset") or r.get("asset") is None)
        kind = "same" if same else f"{r['verdict']} -> {now['verdict']}"
        changes[kind] += 1
        out.append(
            {
                **{k: r.get(k) for k in ("at", "role", "plant", "text", "path", "verdict", "asset")},
                "now": now,
                "same": same,
            }
        )

    n = len(out)
    print(f"{n} logged requests replayed ({args.log}): {changes['same']} same ({changes['same'] / n:.0%})")
    for kind, count in changes.most_common():
        if kind != "same":
            print(f"  {kind}: {count}")
    for row in [o for o in out if not o["same"]][:20]:
        print(
            f"  - {row['text'][:70]!r} ({row['role']}, {row['plant']}): {row['verdict']} {row['asset'] or ''}"
            f" -> {row['now']['verdict']} {row['now']['asset'] or ''}"
        )
    if args.json:
        args.json.write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(f"Per-row results: {args.json}")


if __name__ == "__main__":
    main()
