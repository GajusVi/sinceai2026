"""The org map behind the People tab (Gajus, Sun 8 Nov): who can see whom, who has an open ticket, and role changes.

- `people(data_dir)`: the roster (steward/roster.py) + the four demo accounts of auth.py, with approved changes applied.
- `visible(viewer, people)`: a builder sees the whole company, a manager their own plants (and granted ones),
  a worker nobody.
- `tickets(inbox)`: open tickets per username, read from the shared inbox (steward/inbox.py): approvals a person sent to
  the BI team and floor requests they made or joined. A ticket is a notification, never an edit.
- `Changes`: a manager PROPOSES a change (department, sub-role, boss, plant); a builder approves or declines it; every
  step is one line in people_journal.jsonl. Approved changes are stored as overrides and applied on top of the
  roster, so
  the committed roster file never changes.
No model is involved: access is rule-based, like steward/auth.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from .auth import COMPANY, User
from .roster import PLANTS, Person, load

CHANGES_FILE = "people_changes.json"  # open + decided proposals, and the overrides they produced
JOURNAL_FILE = "people_journal.jsonl"  # append-only trail
EDITABLE = ("department", "sub_role", "reports_to", "plant")  # what a change may touch
_LOCK = threading.Lock()
DEMO_SUB_ROLES = {"Builder12": "BI team", "Manager07": "Site head", "Worker21": "Shift lead", "Worker22": "Technician"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def demo_people() -> list[Person]:
    """The four demo accounts of auth.py as people, so the map shows them next to the generated roster."""
    from .auth import _ACCOUNTS, DEMO_ACCOUNTS

    demo = {name for name, _, _ in DEMO_ACCOUNTS}  # auth also holds the roster logins: count each person once
    out = []
    for username, (_, u) in _ACCOUNTS.items():
        if username not in demo:
            continue
        out.append(
            Person(
                username,
                u.name,
                u.role,
                DEMO_SUB_ROLES.get(username, ""),
                u.plant,
                u.department or "",
                "",
                u.location,
                synthetic=True,
            )
        )
    return out


def people(data_dir: Path | None = None) -> list[Person]:
    """Roster + demo accounts, approved overrides applied."""
    base = demo_people() + load()
    overrides = Changes(data_dir).overrides() if data_dir is not None else {}
    return [replace(p, **overrides[p.username]) if p.username in overrides else p for p in base]


def visible(viewer: User, everyone: list[Person]) -> list[Person]:
    """What this user may see on the map. Workers do not get the tab."""
    if viewer.role == "builder":
        return list(everyone)
    if viewer.role == "management":
        plants = set(viewer.plants if viewer.plants != COMPANY else PLANTS)
        return [p for p in everyone if p.role != "builder" and p.plant in plants]
    return []


def tickets(inbox) -> dict[str, list[dict]]:
    """username -> open tickets [{kind, text, at}], from the shared inbox. Approvals sent to the BI team and floor
    requests (the requester and anyone who joined it)."""
    out: dict[str, list[dict]] = {}
    for a in inbox.open_approvals():
        out.setdefault(a["username"], []).append({"kind": "approval", "text": a["question"], "at": a.get("at", "")})
    for r in inbox.floor("open"):
        row = {"kind": "request", "text": r.get("need", ""), "at": r.get("at", "")}
        for username in [r["username"], *r.get("also", [])]:
            out.setdefault(username, []).append(row)
    return out


# -- cluster-map layout ------------------------------------------------------------------------------------------------
@dataclass
class Node:
    id: str
    label: str
    kind: str  # company | plant | department | person
    x: float
    y: float
    parent: str = ""
    username: str = ""
    role: str = ""
    sub_role: str = ""
    tickets: int = 0
    # frames (plant / department blocks) also carry their box
    w: float = 0.0
    h: float = 0.0


COLS = 5  # dots per row inside a block
BLOCK_W = COLS + 0.8
PAD = 0.9  # space around a block


def _block(
    nodes: list[Node],
    plant: str,
    label: str,
    members: list[Person],
    x0: float,
    y0: float,
    ticket_map: dict[str, list[dict]],
    cols: int = COLS,
) -> float:
    """One block of dots (a department, the managers, the BI team). Returns its height."""
    ordered = sorted(members, key=lambda m: (m.sub_role, m.username))
    rows = max(1, -(-len(ordered) // cols))
    for i, m in enumerate(ordered):
        nodes.append(
            Node(
                f"p:{m.username}",
                m.name,
                "person",
                x0 + 0.5 + (i % cols),
                y0 + 1.3 + (i // cols),
                f"d:{plant}:{label}",
                m.username,
                m.role,
                m.sub_role,
                len(ticket_map.get(m.username, [])),
            )
        )
    h = rows + 1.7
    nodes.append(Node(f"d:{plant}:{label}", label, "department", x0, y0, f"pl:{plant}", w=cols + 0.8, h=h))
    return h


def layout(shown: list[Person], ticket_map: dict[str, list[dict]]) -> list[Node]:
    """The whole org on one screen. One column per plant (managers on top, then a 2 x N grid of department blocks),
    then the BI team. Each person is one dot in their department block: dots are ordered by sub-role."""
    nodes: list[Node] = []
    x = 0.0
    top = 2.2  # room for the plant heading
    plants = [p for p in PLANTS if any(q.plant == p and q.role != "builder" for q in shown)]
    for plant in plants:
        in_plant = [q for q in shown if q.plant == plant and q.role != "builder"]
        managers = [q for q in in_plant if q.role == "management"]
        depts = sorted({q.department for q in in_plant if q.role == "worker"})
        per_row = 2 if len(depts) > 1 else 1
        y = top
        if managers:
            y += _block(nodes, plant, "Management", managers, x, y, ticket_map) + 0.6
        row_h = 0.0
        for i, dept in enumerate(depts):
            col = i % per_row
            if col == 0 and i:
                y += row_h + 0.6
                row_h = 0.0
            h = _block(
                nodes,
                plant,
                dept,
                [q for q in in_plant if q.role == "worker" and q.department == dept],
                x + col * (BLOCK_W + 0.6),
                y,
                ticket_map,
            )
            row_h = max(row_h, h)
        width = per_row * BLOCK_W + (per_row - 1) * 0.6
        nodes.append(Node(f"pl:{plant}", f"{plant} · {len(in_plant)}", "plant", x, 0.0, "co", w=width, h=y + row_h))
        x += width + PAD * 1.4
    builders = [q for q in shown if q.role == "builder"]
    if builders:
        _block(nodes, "BI team", "Builders", builders, x, top, ticket_map)
        nodes.append(Node("pl:BI team", f"BI team · {len(builders)}", "plant", x, 0.0, "co", w=BLOCK_W, h=top + 3.5))
        x += BLOCK_W
    if nodes:
        nodes.append(Node("co", f"Bayer Pharma · {len(shown)} people", "company", 0.0, -1.2, w=x))
    return nodes


# -- proposals --------------------------------------------------------------------------------------------------------
class Changes:
    """Role-change proposals and the overrides they produce. One JSON file, written atomically under a process lock
    (same pattern as steward/inbox.py)."""

    def __init__(self, data_dir: Path | None):
        self.dir = Path(data_dir) if data_dir is not None else None
        self.path = self.dir / CHANGES_FILE if self.dir else None

    def _read(self) -> dict:
        if self.path is None or not self.path.exists():
            return {"proposals": [], "overrides": {}}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"proposals": [], "overrides": {}}

    def _write(self, data: dict) -> None:
        assert self.path is not None
        self.dir.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)

    def _journal(self, row: dict) -> None:
        with (self.dir / JOURNAL_FILE).open("a", encoding="utf-8") as f:  # type: ignore[union-attr]
            f.write(json.dumps({**row, "at": _now()}, ensure_ascii=False) + "\n")

    def overrides(self) -> dict[str, dict]:
        return self._read()["overrides"]

    def proposals(self, status: str | None = "open") -> list[dict]:
        return [p for p in self._read()["proposals"] if status is None or p["status"] == status]

    def journal(self) -> list[dict]:
        path = self.dir / JOURNAL_FILE if self.dir else None
        if path is None or not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def check(self, proposer: User, target: Person, field: str, value: str) -> str:
        """Why this proposal is not allowed, or "" if it is. A manager may propose only for workers and managers of
        their own plants; a builder may change anyone. Builders' own rows are changed by another builder only."""
        if field not in EDITABLE:
            return f"'{field}' cannot be changed here."
        if not value.strip():
            return "A new value is required."
        if proposer.role == "worker":
            return "Workers do not manage roles."
        if target.username == proposer.username:
            return "You cannot change your own role."
        if proposer.role == "management":
            if target.role == "builder":
                return "Builders are managed by the BI team."
            if target.plant not in proposer.plants:
                return f"{target.plant} is not your plant."
        if field == "plant" and value not in PLANTS:
            return f"Unknown plant '{value}'."
        return ""

    def propose(self, proposer: User, target: Person, field: str, value: str, reason: str = "") -> dict:
        """Queue a change. A builder's proposal still needs a second builder (no self-approval)."""
        why = self.check(proposer, target, field, value)
        if why:
            raise ValueError(why)
        row = {
            "id": hashlib.sha256(
                f"{proposer.username}|{target.username}|{field}|{value}|{_now()}".encode()
            ).hexdigest()[:10],
            "status": "open",
            "at": _now(),
            "by": proposer.username,
            "by_role": proposer.role,
            "target": target.username,
            "target_name": target.name,
            "field": field,
            "old": getattr(target, field),
            "new": value.strip(),
            "reason": reason.strip(),
        }

        def change(data: dict):
            if any(
                p["status"] == "open" and p["target"] == row["target"] and p["field"] == field
                for p in data["proposals"]
            ):
                raise ValueError("There is already an open change for that person and field.")
            data["proposals"].append(row)

        self._update(change)
        self._journal({"action": "proposed", **row})
        return row

    def decide(self, proposal_id: str, approver: User, approve: bool, note: str = "") -> dict:
        """A builder (other than the proposer) approves or declines. Approval writes the override."""
        if not approver.can("grant_access"):
            raise ValueError("Only the BI team approves role changes.")
        result: dict = {}

        def change(data: dict):
            row = next((p for p in data["proposals"] if p["id"] == proposal_id and p["status"] == "open"), None)
            if row is None:
                raise ValueError("That change is not open any more.")
            if row["by"] == approver.username:
                raise ValueError("You cannot approve your own proposal.")
            row["status"] = "approved" if approve else "declined"
            row["decided_by"], row["decided_at"], row["note"] = approver.username, _now(), note.strip()
            if approve:
                data["overrides"].setdefault(row["target"], {})[row["field"]] = row["new"]
            result.update(row)

        self._update(change)
        self._journal({"action": result["status"], **result})
        return result

    def apply_now(self, builder: User, target: Person, field: str, value: str, reason: str = "") -> dict:
        """A builder changes someone directly (journaled with the reason): propose + approve in one step, the
        proposer being the builder is allowed only here, so the trail still names who did it."""
        why = self.check(builder, target, field, value)
        if why or not builder.can("grant_access"):
            raise ValueError(why or "Only the BI team changes roles directly.")

        def change(data: dict):
            data["overrides"].setdefault(target.username, {})[field] = value.strip()

        self._update(change)
        row = {
            "action": "applied",
            "by": builder.username,
            "target": target.username,
            "field": field,
            "old": getattr(target, field),
            "new": value.strip(),
            "reason": reason.strip(),
        }
        self._journal(row)
        return row

    def _update(self, change) -> None:
        with _LOCK:
            data = self._read()
            data.setdefault("proposals", [])
            data.setdefault("overrides", {})
            change(data)
            self._write(data)
