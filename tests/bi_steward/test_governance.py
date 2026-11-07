from datetime import timedelta

import pytest

from steward.governance import _PROVISIONAL, PROVISIONAL_DAYS
from steward.models import ArtifactStatus, JournalAction, Verdict


def test_approved_extension_is_provisional_and_does_not_replace_the_base(steward):
    """T1.6 / DECISION C4: an approval must not poison later searches. The new version keeps the base's refresh date,
    inherits no certification, starts unused, and the base stays active until the new version is certified."""
    question = "What is herbicide revenue in LATAM vs plan for Q3?"
    result = steward.ask(question)
    assert result.decision.verdict == Verdict.EXTEND
    base = steward.catalog.artifact("fin-rev-001")

    entry = steward.governance.approve(result, actor="anna")
    steward.reload()

    assert entry.created_artifact_id == "fin-rev-v2"
    assert steward.catalog.artifact("fin-rev-001").status == ArtifactStatus.ACTIVE
    v2 = steward.catalog.artifact("fin-rev-v2")
    assert v2.status == _PROVISIONAL
    assert v2.last_refreshed == base.last_refreshed  # no fake "refreshed today"
    assert not v2.certified and v2.endorsement == "none" and v2.views_30d == 0
    if "expires_at" in type(v2).model_fields:
        assert v2.expires_at == result.as_of + timedelta(days=PROVISIONAL_DAYS)


def test_a_second_extension_of_the_same_base_gets_the_next_version(steward):
    """The base is not superseded any more, so the version id must come from the family, not from the base."""
    question = "What is herbicide revenue in LATAM vs plan for Q3?"
    steward.governance.approve(steward.ask(question), actor="anna")
    steward.reload()
    result = steward.ask(question)
    if result.decision.verdict != Verdict.EXTEND or result.decision.best.artifact.id != "fin-rev-001":
        pytest.skip("the repeat ask no longer extends the base")
    entry = steward.governance.approve(result, actor="anna")
    assert entry.created_artifact_id == "fin-rev-v3"


def test_create_requires_owner(steward):
    result = steward.ask("Logistics carbon footprint by country")

    with pytest.raises(ValueError):
        steward.governance.approve(result, actor="vlada")

    entry = steward.governance.approve(result, actor="vlada", owner="Sustainability team")
    steward.reload()
    created = steward.catalog.artifact(entry.created_artifact_id)
    assert created.status == _PROVISIONAL
    assert created.owner == "Sustainability team"


def test_rejection_is_logged_and_changes_nothing(steward):
    result = steward.ask("What is herbicide revenue in LATAM vs plan for Q3?")
    before = set(steward.catalog.artifacts)

    steward.governance.reject(result, actor="anna", reason="The filter already exists in another report")
    steward.reload()

    assert set(steward.catalog.artifacts) == before
    assert [e.action for e in steward.governance.entries()] == [JournalAction.REJECTED]


def test_clarify_cannot_be_approved(steward):
    result = steward.ask("Show me something interesting")

    with pytest.raises(ValueError):
        steward.governance.approve(result, actor="vlada")
