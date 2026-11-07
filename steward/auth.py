"""Mock login + role permissions for the demo (agreed with Gajus, Sat 7 Nov 16:00). NOT real authentication.

Logging in detects the user's role, plant, location and department; the app shows and allows only what the role may do.
Roles (Panu Q&A: viewers on the production floor vs. builders in IT, plus management):
  worker      one plant, one department. Views what the plant offers, short "soft" grill, reuse only.
              Other departments of the SAME plant and tier: by request. Other plants: never directly,
              only what their manager shares.
  management  one plant, fully. Full grill-me (the AI drafts, a builder approves).
              Other plants and the whole company: by request, granted by a builder.
  builder     IT / BI team. Whole company. Runs the AI to build and edit, approves (incl. AI drafts it asked for,
              the AI is the maker, the builder the checker), grants access, maintains the estate.
Demo shortcut: ANY builder may grant ANY access request. Future: only the builder who owns that data
(the other plant's BI team), see NOTES.md 2026-11-07 16:05.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field
from typing import Literal

Role = Literal["worker", "management", "builder"]
COMPANY = "company"  # scope value: every plant

ACTIONS: dict[Role, frozenset[str]] = {
    "worker": frozenset({"view", "ask", "request_access"}),
    "management": frozenset({"view", "ask", "draft", "request_access", "view_journal"}),
    "builder": frozenset({
        "view", "ask", "draft", "expert_mode", "approve", "edit", "maintain", "grant_access", "view_journal",
    }),
}


@dataclass(frozen=True)
class User:
    username: str
    name: str
    role: Role
    plant: str  # home plant: "Plant-A" .. "Plant-C", "External-CMO" (Supply_Operations.supply_source)
    location: str
    department: str | None = None  # workers only: "Warehouse Ops", "Equipment Ops", ...
    extra_plants: tuple[str, ...] = field(default_factory=tuple)  # management: plants granted by a builder

    @property
    def label(self) -> str:
        """Who did it, for the journal: username + role."""
        return f"{self.username} ({self.role})"

    def can(self, action: str) -> bool:
        return action in ACTIONS[self.role]

    @property
    def plants(self) -> list[str] | str:
        """Plants whose catalog this user can open now. COMPANY = all."""
        if self.role == "builder":
            return COMPANY
        return [self.plant, *self.extra_plants] if self.role == "management" else [self.plant]


# Demo accounts. Passwords are in the clear on purpose: this is a labelled mock, not security.
_ACCOUNTS: dict[str, tuple[str, User]] = {
    "Builder12": ("Admin123", User("Builder12", "BI team (IT)", "builder", "Plant-A", "BI & Analytics, HQ")),
    "Manager07": ("Manage123", User("Manager07", "Site head", "management", "Plant-B", "Plant-B site office")),
    "Worker21": ("Worker123", User("Worker21", "Shift lead", "worker", "Plant-A", "Plant-A floor", "Warehouse Ops")),
    "Worker22": ("Worker123", User("Worker22", "Technician", "worker", "Plant-A", "Plant-A floor", "Equipment Ops")),
}
DEMO_ACCOUNTS = [(name, pw, user.role) for name, (pw, user) in _ACCOUNTS.items()]  # shown on the login screen


def login(username: str, password: str) -> User | None:
    """The account for these credentials, or None. Username is case-insensitive, password is not."""
    match = next((v for k, v in _ACCOUNTS.items() if k.lower() == username.strip().lower()), None)
    if match is None:
        return None
    expected, user = match
    return user if hmac.compare_digest(expected.encode(), password.encode()) else None


def can_request(user: User, plant: str, department: str | None = None) -> tuple[bool, str]:
    """May this user ask for access to (plant, department)? Returns (allowed, reason in plain words)."""
    if user.role == "builder":
        return False, "Builders already see the whole company."
    if user.role == "worker":
        if plant != user.plant:
            return False, "Other plants are not requested directly: your manager shares what you need."
        if department in (None, user.department):
            return False, "You already see your own department."
        return True, f"Request {department} at {plant}: same plant and tier, a builder approves."
    if plant == COMPANY or plant not in user.plants:
        return True, f"Request {'the whole company' if plant == COMPANY else plant}: a builder approves."
    return False, "You already see your own plant in full."


def can_see(user: User, product_scope: str, market_scope: str, supply: list[tuple[str, str, str]]) -> bool:
    """Catalog visibility of one asset. supply = (product_name, market_id, site) rows from Supply_Operations.
    An asset belongs to the plants that supply its product x market scope. All Pharma + Global = company-wide:
    builders only (or management with a company grant). Assets carry no department in the data pack, so a
    worker sees the whole own-plant slice; department-level filtering needs a department tag (future)."""
    if user.plants == COMPANY or COMPANY in user.extra_plants:
        return True
    product_all, market_all = product_scope in ("", "All Pharma"), market_scope in ("", "Global")
    if product_all and market_all:
        return False
    sites = {
        site for product, market, site in supply
        if (product_all or product == product_scope) and (market_all or market == market_scope)
    }
    return bool(sites & set(user.plants))


def can_grant(approver: User) -> bool:
    """Demo: any builder grants any request. Future: only the builder who owns the requested data."""
    return approver.can("grant_access")
