"""data/holdout/verdicts.jsonl (M5): hand-labelled before any threshold tuning. Checks shape and that every named asset exists."""

import glob
import json
from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "data" / "holdout" / "verdicts.jsonl"
VERDICTS = {"REUSE", "EXTEND", "CREATE", "CLARIFY", "CONSOLIDATE", "NOT_FEASIBLE"}


def _rows():
    return [json.loads(line) for line in PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_shape_and_coverage():
    rows = _rows()
    assert len(rows) >= 20
    assert len({r["id"] for r in rows}) == len(rows)
    for r in rows:
        assert r["verdict"] in VERDICTS, r["id"]
        assert r["question"].strip() and r["why"].strip()
        assert r["context"] is None or set(r["context"]) == {"product", "market"}
        # a best asset only where the verdict builds on one
        assert (r["artifact_id"] is not None) == (r["verdict"] in {"REUSE", "EXTEND"}), r["id"]
    templates = Counter(r["template"] for r in rows if r["template"])
    assert sorted(templates) == list(range(1, 11)) and set(templates.values()) == {2}
    assert Counter(r["verdict"] for r in rows)["REUSE"] >= 3


def test_named_assets_exist_and_are_power_bi():
    files = glob.glob(str(ROOT / "data" / "bayer" / "*.xlsx"))
    if not files:
        pytest.skip("data pack not present")
    assets = pd.read_excel(files[0], sheet_name="Analytics_Assets").set_index("asset_id")
    for r in _rows():
        if r["artifact_id"]:
            assert r["artifact_id"] in assets.index, r["id"]
            assert assets.loc[r["artifact_id"], "platform"] == "Power BI", r["id"]
