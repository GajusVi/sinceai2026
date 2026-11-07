"""Mock login + role permissions (steward/auth.py): the agreed role model, Sat 7 Nov 16:00."""

from steward.auth import COMPANY, can_grant, can_request, can_see, login

SUPPLY = [("Nubeqa", "FR", "Plant-B"), ("Nubeqa", "IT", "Plant-C"), ("Xarelto", "DE", "Plant-A")]


def test_catalog_shows_own_plant_slice_company_wide_for_builders_only():
    worker, manager = login("Worker21", "Worker123"), login("Manager07", "Manage123")
    builder = login("Builder12", "Admin123")
    assert can_see(worker, "Xarelto", "DE", SUPPLY) and not can_see(worker, "Nubeqa", "FR", SUPPLY)
    assert can_see(manager, "Nubeqa", "Global", SUPPLY)  # Nubeqa in any market Plant-B supplies
    assert not can_see(manager, "Nubeqa", "IT", SUPPLY)  # Plant-C's slice: by request
    assert not can_see(manager, "All Pharma", "Global", SUPPLY)  # company-wide: through a builder
    assert can_see(builder, "All Pharma", "Global", SUPPLY)


def test_login_detects_role_plant_department():
    user = login("builder12", "Admin123")  # username case-insensitive
    assert user and user.role == "builder" and user.plants == COMPANY
    worker = login("Worker21", "Worker123")
    assert worker and (worker.role, worker.plant, worker.department) == ("worker", "Plant-A", "Warehouse Ops")


def test_wrong_password_or_user_is_refused():
    assert login("Builder12", "admin123") is None  # password is case-sensitive
    assert login("Nobody", "Admin123") is None


def test_only_builders_approve_maintain_and_use_expert_mode():
    builder, manager = login("Builder12", "Admin123"), login("Manager07", "Manage123")
    worker = login("Worker21", "Worker123")
    for action in ("approve", "maintain", "expert_mode", "grant_access"):
        assert builder.can(action) and not manager.can(action) and not worker.can(action)
    assert manager.can("draft") and not worker.can("draft")  # management gets the full grill-me, workers reuse only


def test_worker_requests_other_departments_of_own_plant_only():
    worker = login("Worker21", "Worker123")
    assert can_request(worker, "Plant-A", "Equipment Ops")[0]
    assert not can_request(worker, "Plant-A", "Warehouse Ops")[0]  # own department
    allowed, reason = can_request(worker, "Plant-B", "Equipment Ops")
    assert not allowed and "manager" in reason  # other plants only through their manager


def test_management_requests_other_plants_and_company_builder_grants():
    manager = login("Manager07", "Manage123")
    assert not can_request(manager, "Plant-B")[0]  # own plant is already full
    assert can_request(manager, "Plant-C")[0] and can_request(manager, COMPANY)[0]
    assert can_grant(login("Builder12", "Admin123")) and not can_grant(manager)
