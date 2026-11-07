"""BI Steward evaluation (L8). Everything printed and written to eval/results.json comes from running the code.

Sections
  verdict   labelled cases -> verdict accuracy, best-asset accuracy, confusion matrix, FALSE-REUSE (the headline)
  intent    data/holdout/requests_intent.jsonl (40 hand-checked rows) -> precision/recall/F1 of metrics, products, places
  estate    all 150 Business_Requests through ask + build (rules mode) -> % resolved without a new dashboard,
            spec lint pass rate, lifecycle flag counts

Labelled verdict cases come from four sources, all independent of the engine's output:
  golden     tests/bi_steward/golden_datapack.json  (the verdict contract; written while tuning, so NOT a hold-out)
  blocker    hold-out rows whose labelled metadata_severity is "blocker": text and request metadata disagree -> CLARIFY
  negative   inputs that must never become a dashboard (junk, unknown products, injection): gold = no build
  holdout    data/holdout/verdicts.jsonl (M5, labelled by hand BEFORE tuning): {id, question, context, verdict, artifact_id}
             Missing file = reported as "pending", never silently skipped.

FALSE-REUSE = the code said REUSE (or REUSE on the wrong asset) where the label says otherwise. Rate = false REUSE answers
divided by the labelled cases whose verdict is not REUSE. The business risk it measures: telling someone to use a report
that does not answer their question.

Usage: STEWARD_CATALOG=datapack python eval/eval_steward.py [--no-estate] [--out eval/results.json]
Only Margiris commits eval/results.json (it is also the file the legacy Proof tab reads).
"""

# ruff: noqa: E501
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import Counter
from dataclasses import replace
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from steward import Steward  # noqa: E402
from steward.config import Settings  # noqa: E402
from steward.models import Verdict  # noqa: E402

BUILDS = {Verdict.REUSE.value, Verdict.EXTEND.value, Verdict.CREATE.value, Verdict.CONSOLIDATE.value}
VERDICTS = [v.value for v in Verdict]
NO_BUILD = "NO_BUILD"  # gold for negatives: any verdict except the four builds is correct


def steward() -> Steward:
    os.environ["STEWARD_CATALOG"] = "datapack"  # here, not at import: tests import this module
    settings = replace(Settings.from_env(), use_llm="off", as_of=date(2026, 11, 6))
    return Steward(settings=settings, data_dir=ROOT / "data" / "steward" / "eval")


# -- labelled cases ---------------------------------------------------------------------------------------------


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def negative_inputs() -> list[str]:
    """The must-not-build list lives in the stress test: one list, two users."""
    path = ROOT / "tests" / "bi_steward" / "test_nontechnical_stress.py"
    spec = importlib.util.spec_from_file_location("stress_cases", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return list(module.NEVER_BUILD)


def labelled_cases() -> tuple[list[dict], dict]:
    cases: list[dict] = []
    for g in json.loads((ROOT / "tests" / "bi_steward" / "golden_datapack.json").read_text(encoding="utf-8")):
        cases.append(
            {
                "source": "golden",
                "id": g["question"][:40],
                "text": g["question"],
                "context": g.get("context"),
                "gold": g["verdict"],
                "gold_asset": g.get("artifact_id"),
            }
        )
    for r in _jsonl(ROOT / "data" / "holdout" / "requests_intent.jsonl"):
        if r["metadata_severity"] == "blocker":
            ctx = {"product": r["product_context"], "market": r["market_context"]}
            cases.append(
                {
                    "source": "blocker",
                    "id": r["request_id"],
                    "text": r["text"],
                    "context": ctx,
                    "gold": "CLARIFY",
                    "gold_asset": None,
                }
            )
    for i, text in enumerate(negative_inputs()):
        cases.append(
            {
                "source": "negative",
                "id": f"NEG-{i:02d}",
                "text": text,
                "context": None,
                "gold": NO_BUILD,
                "gold_asset": None,
            }
        )
    pending = {"holdout_verdicts": "pending (M5)"}
    path = ROOT / "data" / "holdout" / "verdicts.jsonl"
    if path.exists():
        rows = _jsonl(path)
        for r in rows:
            cases.append(
                {
                    "source": "holdout",
                    "id": r["id"],
                    "text": r["question"],
                    "context": r.get("context"),
                    "gold": r["verdict"],
                    "gold_asset": r.get("artifact_id"),
                }
            )
        pending = {"holdout_verdicts": f"{len(rows)} rows"}
    return cases, pending


def predict(s: Steward, case: dict) -> dict:
    try:
        r = s.ask(case["text"], case["context"])
        return {"verdict": r.decision.verdict.value, "asset": r.decision.best.artifact.id if r.decision.best else None}
    except Exception as e:  # a crash is a miss, not an abort
        return {"verdict": "ERROR", "asset": None, "error": str(e)[:120]}


def is_correct(case: dict, pred: dict) -> bool:
    if case["gold"] == NO_BUILD:
        return pred["verdict"] not in BUILDS and pred["verdict"] != "ERROR"
    if pred["verdict"] != case["gold"]:
        return False
    return not case["gold_asset"] or pred["asset"] == case["gold_asset"]


def is_false_reuse(case: dict, pred: dict) -> bool:
    if pred["verdict"] != "REUSE":
        return False
    return case["gold"] != "REUSE" or bool(case["gold_asset"] and pred["asset"] != case["gold_asset"])


def caveats(rows: list[dict], reuse_said: list[dict]) -> list[str]:
    """What the numbers cannot say yet. Printed next to them, so a 0% is never read as proof."""
    out = []
    if not any(r["gold"] == "REUSE" for r in rows):
        out.append("no labelled case expects REUSE: false-REUSE 0% only shows the code never says REUSE on these cases")
    if not reuse_said:
        out.append("the code answered REUSE on none of the cases: REUSE precision is undefined")
    if not any(r["source"] == "holdout" for r in rows):
        out.append("no hand-labelled hold-out verdicts yet (M5); golden cases were written while tuning")
    return out


def verdict_section(s: Steward) -> dict:
    cases, pending = labelled_cases()
    rows = [{**c, **predict(s, c)} for c in cases]
    for r in rows:
        r["correct"] = is_correct(r, r)
        r["false_reuse"] = is_false_reuse(r, r)
    matrix: dict[str, Counter] = {}
    for r in rows:
        matrix.setdefault(r["gold"], Counter())[r["verdict"]] += 1
    not_reuse = [r for r in rows if r["gold"] != "REUSE"]
    false_reuse = [r for r in rows if r["false_reuse"]]
    reuse_said = [r for r in rows if r["verdict"] == "REUSE"]
    by_source = {}
    for src in sorted({r["source"] for r in rows}):
        part = [r for r in rows if r["source"] == src]
        by_source[src] = {"n": len(part), "accuracy": round(sum(r["correct"] for r in part) / len(part), 3)}
    return {
        "n": len(rows),
        "accuracy": round(sum(r["correct"] for r in rows) / len(rows), 3),
        "by_source": by_source,
        "false_reuse": {
            "count": len(false_reuse),
            "of_labelled_non_reuse": len(not_reuse),
            "rate": round(len(false_reuse) / len(not_reuse), 3) if not_reuse else 0.0,
            "reuse_precision": round(1 - len(false_reuse) / len(reuse_said), 3) if reuse_said else None,
            "cases": [r["id"] for r in false_reuse],
        },
        "confusion_matrix": {gold: dict(row) for gold, row in sorted(matrix.items())},
        "pending": pending,
        "caveats": caveats(rows, reuse_said),
        "misses": [
            {k: r.get(k) for k in ("source", "id", "text", "gold", "gold_asset", "verdict", "asset", "error")}
            for r in rows
            if not r["correct"]
        ],
    }


# -- intent -----------------------------------------------------------------------------------------------------


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return {
        "precision": round(p, 3),
        "recall": round(r, 3),
        "f1": round(2 * p * r / (p + r), 3) if p + r else 0.0,
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def intent_section(s: Steward) -> dict:
    """What the TEXT names, against the hand-checked labels. Not scored, by design: the 'Global' scope marker (labels keep
    it as scope, not a market) and a theme's proposed default metrics (a proposal the user confirms, not a named metric)."""
    from steward.requests import _area_products, xlsx_products

    rows = _jsonl(ROOT / "data" / "holdout" / "requests_intent.jsonl")
    counts = {k: [0, 0, 0] for k in ("metrics", "products", "markets", "regions")}
    exact = 0
    misses = []
    for r in rows:
        intent = s.interviewer.start(r["text"], mode="expert").intent
        normalized = r["text"].lower().replace("’", "").replace("'", "")
        got_all = {
            "metrics": set(s.parser.parse(r["text"]).metrics),
            "products": set(intent.products) | set(_area_products(normalized, xlsx_products())),
            "markets": set(intent.markets) - {"Global"},
            "regions": set(intent.regions),
        }
        row_ok = True
        for name, got in got_all.items():
            want = set(r[f"expected_{'metric_ids' if name == 'metrics' else name}"])
            counts[name][0] += len(got & want)
            counts[name][1] += len(got - want)
            counts[name][2] += len(want - got)
            if got != want:
                row_ok = False
                misses.append({"id": r["request_id"], "field": name, "got": sorted(got), "want": sorted(want)})
        exact += row_ok
    return {
        "n": len(rows),
        "exact_match": round(exact / len(rows), 3),
        "fields": {k: prf(*v) for k, v in counts.items()},
        "misses": misses,
    }


# -- estate (all 150 requests) ----------------------------------------------------------------------------------


def estate_section() -> dict:
    from steward.intent import intent_from_parsed
    from steward.requests import load_requests
    from steward.semantic import feasibility

    s = steward()
    reqs = load_requests()
    flags: Counter = Counter()
    gaps: Counter = Counter()  # governed KPIs with no source data, rendered as labelled gaps (never as a number)
    verdicts: Counter = Counter()
    specs = blocked = errors = 0
    for req in reqs:
        try:
            r = s.build(s.ask(req.text, {"product": req.product_context, "market": req.market_context}))
        except Exception:
            errors += 1
            continue
        verdicts[r.decision.verdict.value] += 1
        if r.decision.verdict.value != "CLARIFY":  # a gap is only meaningful for a request that was understood
            for g in feasibility(intent_from_parsed(r.question, s.catalog)).gaps:
                gaps[f"{g.kpi_id} {g.name}"] += 1
        flags.update(r.decision.flags)
        if r.spec:
            specs += 1
            blocked += any(x.status == "block" for x in r.spec.lint)
    n = len(reqs)
    avoided = sum(verdicts[v] for v in ("REUSE", "EXTEND", "CONSOLIDATE"))
    return {
        "requests": n,
        "errors": errors,
        "verdicts": dict(verdicts),
        "resolved_without_new_dashboard": {"count": avoided, "share": round(avoided / n, 3)},
        "specs_built": specs,
        "spec_lint_pass_rate": round((specs - blocked) / specs, 3) if specs else None,
        "flags": dict(flags),
        "gaps_by_kpi": dict(gaps.most_common()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-estate", action="store_true", help="skip the 150-request run (faster)")
    ap.add_argument("--out", default=str(ROOT / "eval" / "results.json"))
    args = ap.parse_args()

    s = steward()
    result = {
        "as_of": "2026-11-06",
        "mode": "rules (LLM off)",
        "verdict": verdict_section(s),
        "intent": intent_section(s),
    }
    if not args.no_estate:
        result["estate"] = estate_section()
    # Top-level keys the legacy Proof tab (frontend/app.py, make ui-old) reads: n, accuracy, macro_f1, misses.
    # accuracy = verdict accuracy; macro_f1 = mean of the four intent-field F1 scores (not a verdict F1).
    result["n"] = result["verdict"]["n"]
    result["accuracy"] = result["verdict"]["accuracy"]
    result["macro_f1"] = round(sum(x["f1"] for x in result["intent"]["fields"].values()) / 4, 3)
    result["misses"] = result["verdict"]["misses"]
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

    v = result["verdict"]
    fr = v["false_reuse"]
    print(
        f"FALSE-REUSE {fr['count']} of {fr['of_labelled_non_reuse']} labelled non-REUSE cases = {fr['rate']:.1%}"
        f"  (REUSE precision {fr['reuse_precision']})"
    )
    print(f"verdict accuracy {v['accuracy']:.1%} on {v['n']} cases {v['by_source']}  holdout: {v['pending']}")
    for gold, row in v["confusion_matrix"].items():
        print(f"  gold {gold:<12} -> {row}")
    for c in v["caveats"]:
        print(f"  CAVEAT {c}")
    for m in v["misses"]:
        print(f"  MISS [{m['source']}] {m['id']}: gold={m['gold']} said={m['verdict']} {m['text'][:60]!r}")
    i = result["intent"]
    print(
        f"intent exact {i['exact_match']:.1%} on {i['n']}: "
        + "  ".join(f"{k} F1={x['f1']}" for k, x in i["fields"].items())
    )
    if "estate" in result:
        e = result["estate"]
        print(
            f"estate {e['requests']} requests: without a new dashboard {e['resolved_without_new_dashboard']['share']:.1%}"
            f"  lint pass {e['spec_lint_pass_rate']}  verdicts {e['verdicts']}  flags {e['flags']}"
        )
        print(f"  gaps by KPI {e['gaps_by_kpi']}")


if __name__ == "__main__":
    main()
