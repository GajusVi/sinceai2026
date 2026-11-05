"""Hold-out evaluation. Label 20-50 real examples BEFORE tuning prompts, then run after every change.
Usage: python eval/eval.py [--limit N]     (respects DEMO_MODE and the active LLM provider)
Writes eval/results.json (read by the Proof tab) and prints accuracy, macro F1 and misses."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend import ingest, pipeline  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(ROOT / "eval" / "holdout.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    rows = [json.loads(line) for line in Path(args.file).read_text().splitlines() if line.strip()]
    if args.limit:
        rows = rows[: args.limit]
    items = ingest.from_dataframe(pd.DataFrame(rows), text_col="text", id_col="id")
    gold = {r["id"]: r["label"] for r in rows}

    scored = {s.item.id: s for s in pipeline.score_all(items, log=False)}
    y_true = [gold[i] for i in gold]
    y_pred = [scored[i].decision.label for i in gold]

    misses = [
        {
            "id": i,
            "text": scored[i].item.text[:120],
            "gold": gold[i],
            "pred": scored[i].decision.label,
            "confidence": scored[i].decision.confidence,
        }
        for i in gold
        if gold[i] != scored[i].decision.label
    ]
    res = {
        "n": len(y_true),
        "accuracy": accuracy_score(y_true, y_pred),
        "macro_f1": f1_score(y_true, y_pred, average="macro", zero_division=0),
        "sources": dict(Counter(s.source for s in scored.values())),
        "misses": misses,
    }
    (ROOT / "eval" / "results.json").write_text(json.dumps(res, indent=2))
    print(classification_report(y_true, y_pred, zero_division=0))
    print(f"accuracy={res['accuracy']:.3f}  macro_f1={res['macro_f1']:.3f}  n={res['n']}  sources={res['sources']}")
    for m in misses:
        print(f"  MISS {m['id']}: gold={m['gold']} pred={m['pred']} ({m['confidence']:.2f})  {m['text']}")


if __name__ == "__main__":
    main()
