"""W0 -> W9 without the UI: ask, build the spec, approve, and check the journal and the saved spec."""
import json
from dataclasses import replace
from datetime import date

import pytest

from steward import Steward
from steward.config import Settings
from steward.spec import LintResult

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture
def steward(tmp_path, monkeypatch):
    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    return Steward(settings=replace(Settings.from_env(), use_llm="off", data_dir=tmp_path, as_of=date(2026, 11, 6)))


def test_approve_journals_the_spec_hash_and_lint_and_saves_the_spec(steward, tmp_path):
    result = steward.build(steward.ask("Net sales for Eylea in Japan"))
    result.spec.lint = [LintResult(rule_id="RULE-003", status="pass", message="owner set"),
                        LintResult(rule_id="FOCUS", status="warn", message="5 visuals")]
    entry = steward.governance.approve(result, actor="tester")
    assert entry.spec_hash == result.spec.provenance["spec_hash"] != ""
    assert entry.lint == "1 pass, 1 warn, 0 block" and entry.layout_source == "template"
    saved = tmp_path / "specs" / f"{entry.spec_hash}.json"
    assert json.loads(saved.read_text(encoding="utf-8"))["verdict"] == "REUSE"
    assert steward.governance.entries()[-1].spec_hash == entry.spec_hash


def test_a_lint_block_disables_approval(steward, tmp_path):
    result = steward.build(steward.ask("Net sales for Eylea in Japan"))
    result.spec.lint = [LintResult(rule_id="RULE-003", status="block", message="no active owner")]
    with pytest.raises(ValueError, match="lint gate.*RULE-003"):
        steward.governance.approve(result, actor="tester")
    assert steward.governance.entries() == [] and not (tmp_path / "specs").exists()


def test_reject_still_works_and_logs_the_hash(steward):
    result = steward.build(steward.ask("Net sales for Eylea in Japan"))
    entry = steward.governance.reject(result, actor="tester", reason="not now")
    assert entry.spec_hash == result.spec.provenance["spec_hash"] and entry.action.value == "rejected"


def test_extend_on_the_data_pack_approves_end_to_end(steward):
    text = "Create a global Nubeqa dashboard showing sales growth, forecast variance and market access by country."
    result = steward.build(steward.ask(text))
    assert result.decision.verdict.value == "EXTEND" and result.spec
    entry = steward.governance.approve(result, actor="tester", owner=result.spec.owner_id)
    assert entry.spec_hash and entry.verdict.value == "EXTEND"


def test_no_spec_means_the_journal_fields_stay_empty(steward):
    result = steward.ask("Net sales for Eylea in Japan")  # not built
    entry = steward.governance.approve(result, actor="tester")
    assert entry.spec_hash == "" and entry.lint == ""
