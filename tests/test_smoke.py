"""Smoke tests that run with no API key and no network."""

import os

os.environ["DEMO_MODE"] = "1"
os.environ["DB_PATH"] = "/tmp/sinceai_test.db"

from fastapi.testclient import TestClient  # noqa: E402

from backend import audit, ingest, pipeline  # noqa: E402
from backend.config import ROOT  # noqa: E402
from backend.main import app  # noqa: E402
from backend.models import Review  # noqa: E402
from backend.retrieval import Index  # noqa: E402


def test_demo_inputs_score_without_network():
    items = ingest.load_path(ROOT / "demo" / "inputs.jsonl")
    out = pipeline.score_all(items)
    assert len(out) == len(items)
    assert out[0].decision.priority >= out[-1].decision.priority


def test_audit_roundtrip():
    audit.log_review(Review(item_id="X", verdict="approve"))
    assert audit.latest_verdicts()["X"] == "approve"


def test_api_health_and_score():
    c = TestClient(app)
    assert c.get("/health").json()["ok"]
    r = c.post("/score", json=[{"id": "a", "text": "refund my invoice"}])
    assert r.status_code == 200 and r.json()[0]["decision"]["label"] == "billing"


def test_csv_ingest_guesses_columns():
    items = ingest.load("t.csv", b"ticket_id,description,owner\n7,printer broken,ann\n")
    assert items[0].id == "7" and items[0].text == "printer broken" and items[0].meta["owner"] == "ann"


def test_retrieval_returns_best_match():
    idx = Index().build(["refund policy for invoices", "how to reset a password", "server outage runbook"])
    assert "password" in idx.search("I forgot my password", k=1)[0][2]


def test_ui_scores_and_reviews_without_errors():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "frontend" / "app.py"), default_timeout=60).run()
    assert not at.exception
    at.button[0].click().run()  # "Score items"
    assert not at.exception
    approve = next(b for b in at.button if b.label == "Approve")
    approve.click().run()
    assert not at.exception
    assert any(m.label == "Reviewed" and m.value == "1" for m in at.metric)
