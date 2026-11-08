"""Mega backtest: 100 workers + 10 managers + 1 builder use the app for weeks, on the real and the 5,000-asset pack.

    .venv/Scripts/python.exe eval/mega_backtest.py                  # real 40 working days, large 20, rules mode
    .venv/Scripts/python.exe eval/mega_backtest.py --pack real --days 10
    .venv/Scripts/python.exe eval/mega_backtest.py --llm --days 3   # live model (slow, costs credits)

Each pack runs in its own process (the pack path is read at import: STEWARD_DATAPACK_XLSX). The large pack is built
with tools/make_large_pack.py when it is missing. Output in eval/mega/out/<stamp>/:
  <pack>/interactions.jsonl   one row per interaction: the synthetic usage data field
  <pack>/personas.json, issues.json, summary.json
  READINESS.md                gates, usage insights, issues: is the app ready for the demo?
Nothing outside the output folder is written (journal, inbox, autofill memory, catalog changes live in <pack>/).
Design and gates: eval/mega/README.md.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))
LARGE = ROOT / "data" / "bayer_large" / "Bayer_Large_Synthetic_Pack.xlsx"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pack", choices=["real", "large", "both"], default="both")
    ap.add_argument("--days", type=int, default=40, help="working days on the real pack (default 40)")
    ap.add_argument("--large-days", type=int, default=20, help="working days on the 5,000-asset pack (default 20)")
    ap.add_argument("--report-only", action="store_true", help="rebuild READINESS.md from --out")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--workers", type=int, default=100)
    ap.add_argument("--managers", type=int, default=10)
    ap.add_argument("--llm", action="store_true", help="use the configured live LLM (default: rules only)")
    ap.add_argument("--reload-every", type=int, default=5, help="reload the catalog every N days (approvals)")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--child", choices=["real", "large"], help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.child:
        return child(a)
    out = a.out or ROOT / "eval" / "mega" / "out" / datetime.now().strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    packs = ["real", "large"] if a.pack == "both" else [a.pack]
    if a.report_only:
        return combine(out, [p for p in ("real", "large") if (out / p / "summary.json").exists()], a.llm)
    if "large" in packs and not LARGE.exists():
        print("Large pack missing: building it (tools/make_large_pack.py, about 1-2 min)...")
        subprocess.run([sys.executable, str(ROOT / "tools" / "make_large_pack.py")], check=True, cwd=ROOT)
    for pack in packs:
        env = dict(os.environ)
        if pack == "large":
            env["STEWARD_DATAPACK_XLSX"] = str(LARGE)
        else:
            env.pop("STEWARD_DATAPACK_XLSX", None)
        cmd = [sys.executable, __file__, "--child", pack, "--days", str(a.large_days if pack == "large" else a.days),
               "--seed", str(a.seed),
               "--workers", str(a.workers), "--managers", str(a.managers), "--reload-every", str(a.reload_every),
               "--out", str(out)] + (["--llm"] if a.llm else [])
        print(f"== {pack} pack ==", flush=True)
        t = time.perf_counter()
        code = subprocess.run(cmd, env=env, cwd=ROOT).returncode
        print(f"== {pack} done in {time.perf_counter() - t:.0f} s (exit {code}) ==", flush=True)
    combine(out, packs, a.llm)


def child(a) -> None:
    from mega.report import summarize
    from mega.simulate import Sim

    pack_dir = a.out / a.child
    pack_dir.mkdir(parents=True, exist_ok=True)
    t = time.perf_counter()
    sim = Sim(a.child, a.days, a.seed, pack_dir, llm=a.llm, reload_every=a.reload_every, workers=a.workers,
              managers=a.managers)
    sim.run()
    pbip = [r["pbip"] for r in sim.rows if r.get("pbip")]
    meta = {"days": a.days, "seed": a.seed, "assets": sim.catalog_size, "plants": sim.plants,
            "timings": sim.timings, "determinism": sim.timings.get("determinism", {}), "pbip": pbip,
            "wall_s": round(time.perf_counter() - t, 1), "llm": a.llm}
    with (pack_dir / "interactions.jsonl").open("w", encoding="utf-8") as f:
        for r in sim.rows:
            f.write(json.dumps(r, default=str) + "\n")
    (pack_dir / "personas.json").write_text(json.dumps([p.to_dict() for p in sim.personas], indent=1),
                                            encoding="utf-8")
    (pack_dir / "issues.json").write_text(json.dumps(sim.issues, indent=1, default=str), encoding="utf-8")
    summary = summarize(a.child, sim.rows, sim.issues, sim.loops, meta)
    (pack_dir / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print(f"  [{a.child}] {len(sim.rows)} interactions, met {summary['met_pct']}%, happy {summary['happy_pct']}%, "
          f"{len(sim.issues)} issues, {meta['wall_s']} s")


def combine(out: Path, packs: list[str], llm: bool) -> None:
    from mega.report import gates, markdown, verdict

    summaries, issues = [], []
    for pack in packs:
        path = out / pack / "summary.json"
        if not path.exists():
            print(f"!! {pack}: no summary (the run failed); see the log above")
            continue
        summaries.append(json.loads(path.read_text(encoding="utf-8")))
        issues += json.loads((out / pack / "issues.json").read_text(encoding="utf-8"))
    gs = gates(summaries, llm)
    md = markdown(summaries, gs, issues, llm)
    (out / "READINESS.md").write_text(md, encoding="utf-8")
    (out / "gates.json").write_text(json.dumps({"verdict": verdict(gs), "gates": gs}, indent=1), encoding="utf-8")
    print(f"\nDemo readiness: {verdict(gs)}")
    for g in gs:
        print(f"  {g['status']:5} {g['id']:4} {g['name']}: {g['detail']}")
    print(f"\nReport: {out / 'READINESS.md'}")


if __name__ == "__main__":
    main()
