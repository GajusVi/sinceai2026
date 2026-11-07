"""NOT_FEASIBLE (N6): not in the KPI catalog, or governed without source data. Partly feasible keeps its verdict."""

import pytest
from test_kpi_matching import Pack

from steward.governance import Governance
from steward.models import Verdict

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture(scope="module")
def pack():
    return Pack()


def verdict(pack, text):
    return pack.ask(text).decision


def test_metric_missing_from_the_kpi_catalog(pack):
    d = verdict(pack, "What is the batch yield for Kerendia?")
    assert d.verdict == Verdict.NOT_FEASIBLE and d.best is None
    assert d.evidence[0].rule_id == "DATA" and "batch yield" in d.evidence[0].claim and "KPI-" in d.reasons[1]


def test_governed_kpi_without_data_lists_the_gap_and_a_buildable_alternative(pack):
    d = verdict(pack, "Gross-to-net rate for Nubeqa")
    assert d.verdict == Verdict.NOT_FEASIBLE
    gap = d.evidence[0]
    assert gap.record_ids == ["KPI-034"] and gap.rule_id == "DATA" and "no governed model" in gap.claim
    assert any(e.claim.startswith("Nearest buildable alternative") for e in d.evidence)


def test_partly_feasible_keeps_its_normal_verdict(pack):
    d = verdict(pack, "net sales, gross-to-net and budget variance for Nubeqa")
    assert d.verdict in {Verdict.REUSE, Verdict.EXTEND, Verdict.CREATE}


def test_unmapped_word_next_to_a_real_metric_is_still_clarify(pack):
    assert verdict(pack, "Mgmt inventory coverage").verdict == Verdict.CLARIFY
    assert verdict(pack, "first sales forecast for Kerendia").verdict == Verdict.CLARIFY


def test_nothing_to_approve(pack, tmp_path):
    from datetime import date

    from steward.models import StewardResult

    asked = pack.ask("What is the batch yield for Kerendia?")
    result = StewardResult(question=asked.question, decision=asked.decision, explanation="", as_of=date(2026, 11, 6))
    with pytest.raises(ValueError, match="Nothing to approve"):
        Governance(pack.catalog, tmp_path).approve(result, "tester")
