"""Smoke tests that run with no API key and no network."""

import os
import tempfile

os.environ["DEMO_MODE"] = "1"
os.environ["DB_PATH"] = os.path.join(tempfile.gettempdir(), "sinceai_test.db")

from backend import audit, ingest, pipeline  # noqa: E402
from backend.config import ROOT  # noqa: E402
from backend.models import Review  # noqa: E402


def test_demo_inputs_score_without_network():
    items = ingest.load_path(ROOT / "demo" / "inputs.jsonl")
    out = pipeline.score_all(items)
    assert len(out) == len(items)
    assert out[0].decision.priority >= out[-1].decision.priority


def test_audit_roundtrip():
    audit.log_review(Review(item_id="X", verdict="approve"))
    assert audit.latest_verdicts()["X"] == "approve"


def test_csv_ingest_guesses_columns():
    items = ingest.load("t.csv", b"ticket_id,description,owner\n7,printer broken,ann\n")
    assert items[0].id == "7" and items[0].text == "printer broken" and items[0].meta["owner"] == "ann"
