"""Synthetic org roster for the People tab (Gajus, Sun 8 Nov): 100 workers, 10 managers, 5 builders.

Same logic as steward/auth.py: a worker has one plant and one department, a manager one plant, a builder the whole
company. On top of that each person has a SUB-ROLE (their job: shift lead, technician, site head, governance owner ...)
and a `reports_to` (a worker to a manager of their plant, a manager to the BI lead, builders to nobody).

The data is invented: names are made-up combinations, usernames are Worker101.., Manager101.., Builder101..
(the four demo accounts of auth.py are untouched). Generated once by tools/gen_roster.py into steward/roster.json and
committed, so every machine shows the same people. Passwords follow the demo rule per role (a labelled mock).
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

ROSTER_FILE = Path(__file__).resolve().parent.parent / "steward" / "roster.json"
PLANTS = ("Plant-A", "Plant-B", "Plant-C")
PASSWORDS = {"worker": "Worker123", "management": "Manage123", "builder": "Admin123"}
PREFIX = {"worker": "Worker", "management": "Manager", "builder": "Builder"}

COUNTS = {"worker": 100, "management": 10, "builder": 5}
WORKERS_PER_PLANT = {"Plant-A": 40, "Plant-B": 35, "Plant-C": 25}
MANAGERS_PER_PLANT = {"Plant-A": 4, "Plant-B": 3, "Plant-C": 3}

DEPARTMENT_SUBROLES = {
    "Warehouse Ops": ["Shift lead", "Inventory clerk", "Forklift operator", "Picker"],
    "Equipment Ops": ["Maintenance planner", "Technician", "Line operator", "Reliability engineer"],
    "Quality Ops": ["QA analyst", "Batch reviewer", "Inspector", "Lab technician"],
    "Supply Planning": ["Demand planner", "Supply planner", "Logistics coordinator", "Buyer"],
}
MANAGER_SUBROLES = ["Site head", "Supply lead", "Quality lead", "Operations lead"]
BUILDER_SUBROLES = ["BI lead", "Governance owner", "Data engineer", "Analytics engineer", "Floor-request desk"]

FIRST = [
    "Aino",
    "Mika",
    "Elias",
    "Laura",
    "Jonas",
    "Ieva",
    "Tomas",
    "Sanna",
    "Petra",
    "Matti",
    "Lukas",
    "Greta",
    "Antti",
    "Karolis",
    "Emma",
    "Oskar",
    "Liisa",
    "Marius",
    "Hanna",
    "Viktor",
    "Noora",
    "Dainius",
    "Katja",
    "Robin",
    "Elina",
    "Rasa",
    "Jens",
    "Maija",
    "Andrius",
    "Sofia",
    "Pekka",
    "Agne",
    "Felix",
    "Tuula",
    "Darius",
    "Helena",
    "Juho",
    "Egle",
    "Nils",
    "Riikka",
]
LAST = [
    "Virtanen",
    "Kask",
    "Lindholm",
    "Jankauskas",
    "Berg",
    "Korhonen",
    "Petrauskas",
    "Nieminen",
    "Hartmann",
    "Laine",
    "Vasiliauskas",
    "Hakala",
    "Brandt",
    "Mäkelä",
    "Kazlauskas",
    "Salo",
    "Weiss",
    "Heikkinen",
    "Stankus",
    "Lehtonen",
    "Fischer",
    "Ojala",
    "Paulaitis",
    "Rantanen",
    "Keller",
    "Aalto",
    "Butkus",
    "Turunen",
    "Maier",
    "Saarinen",
]


@dataclass(frozen=True)
class Person:
    username: str
    name: str
    role: str  # worker | management | builder
    sub_role: str
    plant: str  # builders: "Plant-A" (home site, like Builder12) but they see the whole company
    department: str  # workers only, else ""
    reports_to: str  # username, "" for none
    location: str
    synthetic: bool = True

    @property
    def password(self) -> str:
        return PASSWORDS[self.role]

    @property
    def scope(self) -> str:
        return "company" if self.role == "builder" else self.plant


def generate(seed: int = 2026) -> list[Person]:
    """Deterministic: the same seed always gives the same 115 people."""
    from .worker import DEPARTMENTS  # lazy: worker imports a lot

    rng = random.Random(seed)
    names = [f"{first} {last}" for first in FIRST for last in LAST]
    rng.shuffle(names)
    it = iter(names)
    people: list[Person] = []

    builders: list[Person] = []
    for i, sub in enumerate(BUILDER_SUBROLES):
        builders.append(
            Person(
                f"Builder{101 + i}",
                next(it),
                "builder",
                sub,
                "Plant-A",
                "",
                "" if i == 0 else "Builder101",
                "BI & Analytics, HQ",
            )
        )
    people += builders

    managers: dict[str, list[Person]] = {p: [] for p in PLANTS}
    n = 0
    for plant in PLANTS:
        for j in range(MANAGERS_PER_PLANT[plant]):
            m = Person(
                f"Manager{101 + n}",
                next(it),
                "management",
                MANAGER_SUBROLES[j % len(MANAGER_SUBROLES)],
                plant,
                "",
                "Builder101",
                f"{plant} site office",
            )
            managers[plant].append(m)
            n += 1
    people += [m for ms in managers.values() for m in ms]

    n = 0
    for plant in PLANTS:
        for j in range(WORKERS_PER_PLANT[plant]):
            dept = DEPARTMENTS[j % len(DEPARTMENTS)]
            sub = DEPARTMENT_SUBROLES.get(dept, ["Operator"])[(j // len(DEPARTMENTS)) % 4]
            boss = managers[plant][j % len(managers[plant])]
            people.append(
                Person(f"Worker{101 + n}", next(it), "worker", sub, plant, dept, boss.username, f"{plant} floor")
            )
            n += 1
    return people


def save(people: list[Person], path: Path = ROSTER_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"synthetic": True, "people": [asdict(p) for p in people]}, indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load(path: Path = ROSTER_FILE) -> list[Person]:
    """The committed roster, or [] if the file is missing (the app then runs with the four demo accounts only)."""
    if not Path(path).exists():
        return []
    rows = json.loads(Path(path).read_text(encoding="utf-8")).get("people", [])
    return [Person(**r) for r in rows]


def accounts(people: list[Person] | None = None):
    """(username, password, User) for auth.py to add next to its four demo accounts. Lazy import."""
    from .auth import User

    out = []
    for p in people if people is not None else load():
        user = User(p.username, p.name, p.role, p.plant, p.location, p.department or None)  # type: ignore[arg-type]
        out.append((p.username, p.password, user))
    return out
