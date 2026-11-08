"""Mega backtest personas: 100 workers, 10 managers, 1 builder (admin), spread over the pack's plants.

Every persona is a real steward.auth.User (the same object the app gets at login) plus behaviour traits:
  rate      sessions per working day (Poisson mean)
  channels  how they start a session, as weights: button | chat | typeahead | interview | other | expert
  patience  questions they answer before pressing "Skip - use recommended" (managers) or giving up
  savvy     0..1: 1 = types precise governed words, 0 = vague words, typos, wrong plant names
  escalate  probability they hand an unanswered need to the BI team (workers) / send a ruling for approval (managers)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from steward.auth import COMPANY, User

# Worker sub-roles per department: (sub-role, share of the department, rate, channels, patience, savvy, escalate)
WORKER_SUBROLES: dict[str, list[tuple[str, float, float, dict[str, float], int, float, float]]] = {
    "Warehouse Ops": [
        ("Shift lead", 0.3, 1.2, {"button": 5, "chat": 3, "other": 1}, 2, 0.6, 0.35),
        ("Warehouse operator", 0.5, 0.6, {"button": 7, "chat": 2, "other": 0.3}, 1, 0.3, 0.15),
        ("Inventory clerk", 0.2, 0.9, {"button": 4, "chat": 4, "other": 0.7}, 2, 0.7, 0.3),
    ],
    "Equipment Ops": [
        ("Technician", 0.5, 0.7, {"button": 6, "chat": 3, "other": 0.5}, 1, 0.4, 0.3),
        ("Maintenance planner", 0.25, 0.8, {"button": 3, "chat": 4, "other": 1.5}, 2, 0.7, 0.45),
        ("Line supervisor", 0.25, 1.0, {"button": 4, "chat": 4, "other": 1}, 2, 0.6, 0.4),
    ],
    "Quality Ops": [
        ("QA analyst", 0.4, 0.9, {"button": 3, "chat": 5, "other": 1}, 2, 0.8, 0.45),
        ("QC lab technician", 0.4, 0.5, {"button": 6, "chat": 2, "other": 0.5}, 1, 0.4, 0.2),
        ("Batch release officer", 0.2, 0.8, {"button": 4, "chat": 3, "other": 1.5}, 2, 0.7, 0.5),
    ],
    "Supply Planning": [
        ("Supply planner", 0.4, 1.1, {"button": 3, "chat": 5, "other": 1}, 3, 0.8, 0.4),
        ("Demand planner", 0.35, 1.0, {"button": 3, "chat": 5, "other": 0.7}, 3, 0.8, 0.35),
        ("Production scheduler", 0.25, 0.9, {"button": 5, "chat": 3, "other": 1}, 2, 0.6, 0.3),
    ],
}

# Management sub-roles: (sub-role, count of 10, rate, channels, patience, savvy, escalate, company_wide)
MANAGER_SUBROLES: list[tuple[str, int, float, dict[str, float], int, float, float, bool]] = [
    ("Site head", 3, 0.6, {"interview": 6, "typeahead": 3}, 3, 0.5, 0.7, False),
    ("Operations director", 2, 0.7, {"interview": 6, "typeahead": 2}, 4, 0.7, 0.6, False),
    ("Finance controller", 2, 0.5, {"interview": 5, "typeahead": 3}, 4, 0.9, 0.6, False),
    ("Commercial lead", 2, 0.5, {"interview": 6, "typeahead": 2}, 3, 0.6, 0.5, False),
    ("Shareholder / exec", 1, 0.25, {"interview": 5, "typeahead": 3}, 2, 0.3, 0.4, True),
]


@dataclass
class Persona:
    user: User
    subrole: str
    rate: float
    channels: dict[str, float]
    patience: int
    savvy: float
    escalate: float
    stats: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.user.username

    def to_dict(self) -> dict:
        u = self.user
        return {"username": u.username, "role": u.role, "subrole": self.subrole, "plant": u.plant,
                "department": u.department, "extra_plants": list(u.extra_plants), "rate": self.rate,
                "channels": self.channels, "patience": self.patience, "savvy": self.savvy, "escalate": self.escalate}


def build_personas(plants: list[str], rng: random.Random, workers: int = 100, managers: int = 10) -> list[Persona]:
    """Workers round-robin over plants (production plants weigh 3x the CMO), departments evenly; managers one per
    plant first, then the rest by sub-role. One builder (admin) for the whole company."""
    weighted = [p for p in plants for _ in range(1 if p == "External-CMO" else 3)]
    out: list[Persona] = []
    depts = list(WORKER_SUBROLES)
    for i in range(workers):
        dept = depts[i % len(depts)]
        plant = weighted[(i * 7) % len(weighted)]
        sub = rng.choices(WORKER_SUBROLES[dept], weights=[s[1] for s in WORKER_SUBROLES[dept]])[0]
        name, _, rate, channels, patience, savvy, esc = sub
        user = User(f"W{i + 1:03d}", name, "worker", plant, f"{plant} floor", dept)
        out.append(Persona(user, name, rate * rng.uniform(0.7, 1.3), dict(channels), patience,
                           min(1.0, max(0.0, savvy + rng.uniform(-0.2, 0.2))), esc))
    site_plants = [p for p in plants if p != "External-CMO"] or plants
    n = 0
    for sub, count, rate, channels, patience, savvy, esc, company in MANAGER_SUBROLES:
        for _ in range(count):
            if n >= managers:
                break
            plant = site_plants[n % len(site_plants)]
            extra = (COMPANY,) if company else ()
            user = User(f"M{n + 1:02d}", sub, "management", plant, f"{plant} site office", extra_plants=extra)
            out.append(Persona(user, sub, rate * rng.uniform(0.8, 1.2), dict(channels), patience,
                               savvy, esc))
            n += 1
    admin = User("B01", "BI team (IT)", "builder", site_plants[0], "BI & Analytics, HQ")
    out.append(Persona(admin, "Builder (admin)", 1.0, {"expert": 1}, 5, 1.0, 0.0))
    return out
