"""data/build_probes.py: the probe oracle must stay independent of the engine, deterministic, and match what is on disk."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "build_probes.py"
PROBES = ROOT / "data" / "holdout" / "probes.jsonl"
BASELINE = ROOT / "data" / "holdout" / "probes_baseline.json"


def _rows():
    return [json.loads(line) for line in PROBES.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_oracle_does_not_import_the_engine():
    """`steward` may only be imported inside run_engine; the labels must not be derived from engine code."""
    text = SRC.read_text(encoding="utf-8")
    before_engine = text.split("def run_engine", 1)[0]
    assert not re.search(r"^\s*(from|import)\s+steward", before_engine, re.M)
    assert not re.search(r"^\s*(from|import)\s+backend", text, re.M)


def test_probe_grid_and_labels_are_well_formed():
    rows = _rows()
    assert len(rows) == 980 == 7 * 14 * 10
    assert len({r["id"] for r in rows}) == len(rows)
    for r in rows:
        for rule in ("today", "c2a"):
            e = r[rule]
            assert e["verdict"] in {"REUSE", "EXTEND", "CREATE"} and e["verdict"] in e["acceptable"]
            assert (e["verdict"] == "CREATE") == (not e["assets"])
    # C2=A only removes REUSE options, it never adds one
    for r in rows:
        if r["c2a"]["verdict"] == "REUSE":
            assert r["today"]["verdict"] == "REUSE" and set(r["c2a"]["assets"]) <= set(r["today"]["assets"])


def test_known_reuse_cases_from_the_hand_labelled_holdout():
    by_text = {r["text"]: r for r in _rows()}
    nubeqa_fr = by_text["Nubeqa net sales in France"]
    assert nubeqa_fr["today"]["verdict"] == "REUSE" and "AST-0247" in nubeqa_fr["today"]["assets"]  # H-21
    assert "AST-0292" in by_text["Kerendia demand forecast bias in Finland"]["today"]["assets"]  # H-23 (bias + net sales)


def test_regenerating_gives_the_file_on_disk():
    glob = pytest.importorskip("glob")
    if not glob.glob(str(ROOT / "data" / "bayer" / "*.xlsx")):
        pytest.skip("data pack not present")
    import importlib.util

    spec = importlib.util.spec_from_file_location("build_probes", SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert json.loads(json.dumps(mod.build())) == _rows()


def test_baseline_was_frozen_and_has_both_paths():
    b = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert set(b["summary"]) == {"today/expert", "today/intent", "c2a/expert", "c2a/intent"}
    assert b["engine_commit"] and len(b["per_probe"]) == 980
