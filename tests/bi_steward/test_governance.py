import pytest

from steward.models import ArtifactStatus, JournalAction, Verdict


def test_approved_extension_becomes_reusable(steward):
    question = "What is herbicide revenue in LATAM vs plan for Q3?"
    result = steward.ask(question)
    assert result.decision.verdict == Verdict.EXTEND

    entry = steward.governance.approve(result, actor="anna")
    steward.reload()

    assert entry.created_artifact_id == "fin-rev-v2"
    assert steward.catalog.artifact("fin-rev-001").status == ArtifactStatus.SUPERSEDED
    again = steward.ask(question).decision
    assert again.verdict == Verdict.REUSE
    assert again.best.artifact.id == "fin-rev-v2"


def test_create_requires_owner(steward):
    result = steward.ask("Logistics carbon footprint by country")

    with pytest.raises(ValueError):
        steward.governance.approve(result, actor="vlada")

    entry = steward.governance.approve(result, actor="vlada", owner="Sustainability team")
    steward.reload()
    created = steward.catalog.artifact(entry.created_artifact_id)
    assert created.status == ArtifactStatus.DRAFT
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
