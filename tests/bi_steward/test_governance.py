from datetime import timedelta

import pytest

from steward.governance import _PROVISIONAL, PROVISIONAL_DAYS
from steward.models import ArtifactStatus, JournalAction, Verdict


@pytest.fixture
def steward(tmp_path, monkeypatch):
    """The data pack, whatever the default catalog (T3.7 removes the sample catalog)."""
    from dataclasses import replace
    from datetime import date

    from steward import Steward
    from steward.config import Settings

    monkeypatch.setenv("STEWARD_CATALOG", "datapack")
    settings = replace(Settings.from_env(), use_llm="off", data_dir=tmp_path, as_of=date(2026, 11, 6))
    return Steward(settings=settings)


# Data-pack requests with human labels (eval_steward.labelled_cases): EXTEND of AST-0247, and an honest CREATE.
EXTEND_Q = "Show me net sales, units shipped, market access coverage and forecast variance for Nubeqa in France."
CREATE_Q = "Can we have a new finance dashboard for net sales, gross-to-net and budget variance by product?"


def test_approved_extension_is_provisional_and_does_not_replace_the_base(steward):
    """T1.6 / DECISION C4: an approval must not poison later searches. The new version keeps the base's refresh date,
    inherits no certification, starts unused, and the base stays active until the new version is certified."""
    result = steward.ask(EXTEND_Q)
    assert result.decision.verdict == Verdict.EXTEND
    base = steward.catalog.artifact("AST-0247")

    entry = steward.governance.approve(result, actor="anna")
    steward.reload()

    assert entry.created_artifact_id == "AST-0247-v2"
    assert steward.catalog.artifact("AST-0247").status == ArtifactStatus.ACTIVE
    v2 = steward.catalog.artifact("AST-0247-v2")
    assert v2.status == _PROVISIONAL
    assert v2.last_refreshed == base.last_refreshed  # no fake "refreshed today"
    assert not v2.certified and v2.endorsement == "none" and v2.views_30d == 0
    if "expires_at" in type(v2).model_fields:
        assert v2.expires_at == result.as_of + timedelta(days=PROVISIONAL_DAYS)


def test_a_second_extension_of_the_same_base_gets_the_next_version(steward):
    """The base is not superseded any more, so the version id must come from the family, not from the base."""
    steward.governance.approve(steward.ask(EXTEND_Q), actor="anna")
    steward.reload()
    result = steward.ask(EXTEND_Q)
    if result.decision.verdict != Verdict.EXTEND or result.decision.best.artifact.id != "AST-0247":
        pytest.skip("the repeat ask no longer extends the base")
    entry = steward.governance.approve(result, actor="anna")
    assert entry.created_artifact_id == "AST-0247-v3"


def test_create_requires_owner(steward):
    result = steward.ask(CREATE_Q)
    assert result.decision.verdict == Verdict.CREATE

    with pytest.raises(ValueError):
        steward.governance.approve(result, actor="vlada")

    entry = steward.governance.approve(result, actor="vlada", owner="Sustainability team")
    steward.reload()
    created = steward.catalog.artifact(entry.created_artifact_id)
    assert created.status == _PROVISIONAL
    assert created.owner == "Sustainability team"


def test_rejection_is_logged_and_changes_nothing(steward):
    result = steward.ask(EXTEND_Q)
    before = set(steward.catalog.artifacts)

    steward.governance.reject(result, actor="anna", reason="The filter already exists in another report")
    steward.reload()

    assert set(steward.catalog.artifacts) == before
    assert [e.action for e in steward.governance.entries()] == [JournalAction.REJECTED]


def test_clarify_cannot_be_approved(steward):
    result = steward.ask("Show me something interesting")

    with pytest.raises(ValueError):
        steward.governance.approve(result, actor="vlada")
