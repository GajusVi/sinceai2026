"""Rule parser vs the hand-checked metric labels in data/holdout/requests_intent.jsonl (Martynas T6)."""
import json
from pathlib import Path

import pytest
from test_kpi_matching import Pack

from steward.query_parser import RuleBasedParser

pytestmark = pytest.mark.filterwarnings("ignore")
ROWS = [json.loads(line) for line in (Path(__file__).parents[2] / "data" / "holdout" / "requests_intent.jsonl").read_text(encoding="utf-8").splitlines()]


def test_rule_parser_metric_ids_match_holdout_labels():
    parser = RuleBasedParser(Pack().catalog)
    wrong = [r["request_id"] for r in ROWS if set(parser.parse(r["text"]).metrics) != set(r["expected_metric_ids"])]
    assert len(ROWS) == 40 and wrong == []
