"""People tab data layer (Gajus, 8 Nov): roster counts, who sees whom, ticket badges, role changes with approval."""

from collections import Counter

import pytest

from steward import orgmap, roster
from steward.auth import login
from steward.inbox import Inbox

MANAGER, BUILDER, WORKER = (
    login("Manager07", "Manage123"),
    login("Builder12", "Admin123"),
    login("Worker21", "Worker123"),
)


def test_roster_is_100_10_5_with_unique_names_and_logins():
    people = roster.load()
    assert Counter(p.role for p in people) == {"worker": 100, "management": 10, "builder": 5}
    assert len({p.username for p in people}) == 115 == len({p.name for p in people})
    assert all(p.department for p in people if p.role == "worker") and all(p.sub_role for p in people)
    assert all(p.reports_to in {q.username for q in people} | {""} for p in people)


def test_roster_is_deterministic_and_matches_the_committed_file():
    assert roster.generate() == roster.load()


def test_roster_accounts_use_the_role_password_rule():
    for username, password, user in roster.accounts():
        assert password == roster.PASSWORDS[user.role] and user.username == username


def test_builder_sees_everyone_manager_own_plant_worker_nobody(tmp_path):
    everyone = orgmap.people(tmp_path)
    assert len(everyone) == 115 + 4
    assert len(orgmap.visible(BUILDER, everyone)) == len(everyone)
    mine = orgmap.visible(MANAGER, everyone)
    assert mine and {p.plant for p in mine} == {"Plant-B"} and all(p.role != "builder" for p in mine)
    assert orgmap.visible(WORKER, everyone) == []


def test_tickets_come_from_the_shared_inbox(tmp_path):
    inbox = Inbox(tmp_path)
    inbox.add_floor(
        {"kind": "report", "username": "Worker22", "need": "line downtime", "status": "open"}, lambda rows, e: None
    )
    inbox.add_floor(
        {"kind": "report", "username": "Worker101", "need": "line downtime", "status": "open"},
        lambda rows, e: rows[0] if rows else None,
    )  # joins the first
    t = orgmap.tickets(inbox)
    assert t["Worker22"][0]["text"] == "line downtime" and "Worker101" in t


def test_layout_has_one_node_per_person_plus_groups(tmp_path):
    shown = orgmap.visible(BUILDER, orgmap.people(tmp_path))
    nodes = orgmap.layout(shown, {"Worker101": [{"kind": "request", "text": "x", "at": ""}]})
    assert sum(n.kind == "person" for n in nodes) == len(shown)
    assert {n.kind for n in nodes} == {"company", "plant", "department", "person"}
    pts = [(n.x, n.y) for n in nodes if n.kind == "person"]
    assert len(set(pts)) == len(pts)  # no two people on one spot
    assert next(n for n in nodes if n.username == "Worker101").tickets == 1


def test_manager_proposes_builder_approves_override_applies_and_is_journaled(tmp_path):
    changes = orgmap.Changes(tmp_path)
    target = next(p for p in orgmap.people(tmp_path) if p.role == "worker" and p.plant == "Plant-B")
    row = changes.propose(MANAGER, target, "sub_role", "Shift lead", "covering nights")
    assert changes.proposals() and orgmap.people(tmp_path) and row["old"] == target.sub_role
    assert (
        next(p for p in orgmap.people(tmp_path) if p.username == target.username).sub_role == target.sub_role
    )  # not yet
    changes.decide(row["id"], BUILDER, True, "ok")
    assert next(p for p in orgmap.people(tmp_path) if p.username == target.username).sub_role == "Shift lead"
    assert [j["action"] for j in changes.journal()] == ["proposed", "approved"]


@pytest.mark.parametrize(
    "who,target_filter,field,value,msg",
    [
        (MANAGER, lambda p: p.plant == "Plant-A" and p.role == "worker", "department", "Quality Ops", "not your plant"),
        (MANAGER, lambda p: p.role == "builder", "sub_role", "x", "Builders are managed"),
        (MANAGER, lambda p: p.username == "Manager07", "sub_role", "x", "your own role"),
        (WORKER, lambda p: p.plant == "Plant-A", "sub_role", "x", "Workers do not"),
        (MANAGER, lambda p: p.plant == "Plant-B" and p.role == "worker", "username", "x", "cannot be changed"),
    ],
)
def test_proposals_the_rules_refuse(tmp_path, who, target_filter, field, value, msg):
    target = next(p for p in orgmap.people(tmp_path) if target_filter(p))
    with pytest.raises(ValueError, match=msg):
        orgmap.Changes(tmp_path).propose(who, target, field, value)


def test_only_builders_decide_and_never_their_own_and_not_twice(tmp_path):
    changes = orgmap.Changes(tmp_path)
    target = next(p for p in orgmap.people(tmp_path) if p.role == "worker" and p.plant == "Plant-B")
    row = changes.propose(MANAGER, target, "department", "Quality Ops")
    with pytest.raises(ValueError, match="BI team"):
        changes.decide(row["id"], MANAGER, True)
    with pytest.raises(ValueError, match="already an open"):
        changes.propose(MANAGER, target, "department", "Supply Planning")
    changes.decide(row["id"], BUILDER, False, "no")
    with pytest.raises(ValueError, match="not open"):
        changes.decide(row["id"], BUILDER, True)
    assert next(p for p in orgmap.people(tmp_path) if p.username == target.username).department == target.department


def test_a_builder_can_apply_directly_with_a_journal_line(tmp_path):
    changes = orgmap.Changes(tmp_path)
    target = next(p for p in orgmap.people(tmp_path) if p.role == "worker")
    changes.apply_now(BUILDER, target, "sub_role", "Technician", "audit")
    assert next(p for p in orgmap.people(tmp_path) if p.username == target.username).sub_role == "Technician"
    assert changes.journal()[-1]["action"] == "applied" and changes.journal()[-1]["by"] == "Builder12"
