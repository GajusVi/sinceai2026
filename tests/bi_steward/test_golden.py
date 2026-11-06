import json
from pathlib import Path

import pytest

GOLDEN = json.loads((Path(__file__).parent / "golden_questions.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", GOLDEN, ids=[c["question"] for c in GOLDEN])
def test_golden_question(steward, case):
    decision = steward.ask(case["question"]).decision

    assert decision.verdict.value == case["verdict"]
    best_id = decision.best.artifact.id if decision.best else None
    assert best_id == case["artifact_id"]
    if "conflicts" in case:
        assert sorted(c.artifact_id for c in decision.conflicts) == sorted(case["conflicts"])
