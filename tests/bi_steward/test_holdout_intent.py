import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYS = {"request_id", "text", "product_context", "market_context", "expected_products", "expected_markets",
        "expected_regions", "expected_metric_ids", "expected_grain", "metadata_conflict", "notes"}


def _rows():
    lines = (ROOT / "data" / "holdout" / "requests_intent.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines]


def test_holdout_has_40_rows_four_per_template():
    rows = _rows()
    assert len(rows) == 40 and len({r["request_id"] for r in rows}) == 40
    assert all(set(r) == KEYS for r in rows)
    products = ["Nubeqa", "Kerendia", "Eylea", "Xarelto", "Lynkuet", "Beyonttra", "Hyrnuo"]
    def tmpl(t):
        for p in products:
            t = t.replace(p, "<P>")
        return t
    counts = Counter(tmpl(r["text"]) for r in rows)
    assert len(counts) == 10 and set(counts.values()) == {4}


def test_expected_values_are_valid_catalog_ids():
    metrics = {m["id"] for m in json.loads((ROOT / "catalog/bayer/metrics.json").read_text(encoding="utf-8"))}
    regions = set(json.loads((ROOT / "catalog/bayer/regions.json").read_text(encoding="utf-8")))
    for r in _rows():
        assert set(r["expected_metric_ids"]) <= metrics
        assert set(r["expected_regions"]) <= regions
        assert all(p in r["text"] or p in ("Nubeqa", "Hyrnuo") for p in r["expected_products"])
        assert r["expected_grain"] in ("month", "quarter")
