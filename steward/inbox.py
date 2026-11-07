"""Shared inbox (DECISION T2.3, gajus-chain N4): every handoff between people in one store in the data dir.

Before this, the approval queue, the floor requests and the access grants lived in one browser's st.session_state,
so a request from a manager's browser never reached a builder's browser. Now:
- approvals: a ruling a worker or manager sends to the BI team; a builder reviews it, then approves or sends it back;
- floor:     requests from the production floor (access to another department's data, or a missing number);
- grants:    departments a builder shared with a worker;
- notices:   what happened to your request, shown to the requester on their next page load.

One JSON file (`inbox.json`), written atomically under a process lock: a demo store for a few people, not a ticket
system. The journal stays the audit trail (governance.py, floor_requests.jsonl); this file is only the live state.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime
from pathlib import Path

from .models import StewardResult

FILE = "inbox.json"
_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def approval_key(username: str, question: str, verdict: str) -> str:
    """Same person, same question, same verdict = the same request (sending it twice does not queue it twice)."""
    return hashlib.sha256(f"{username}|{question.strip().lower()}|{verdict}".encode()).hexdigest()[:12]


class Inbox:
    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / FILE

    # -- storage -------------------------------------------------------------------------------------------------
    def _read(self) -> dict:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        for key, empty in (("approvals", []), ("floor", []), ("grants", {}), ("notices", {})):
            data.setdefault(key, empty)
        return data

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, self.path)  # atomic: a reader never sees half a file

    def _update(self, change) -> object:
        with _LOCK:
            data = self._read()
            out = change(data)
            self._write(data)
            return out

    # -- approvals -----------------------------------------------------------------------------------------------
    def send(self, result: StewardResult, intent, novice: bool, user) -> str:
        """Queue a ruling for the BI team. Returns its id; an identical open request is not queued twice."""
        key = approval_key(user.username, result.question.text, result.decision.verdict.value)

        def change(data):
            if any(a["id"] == key and a["status"] in ("open", "in_review") for a in data["approvals"]):
                return key
            data["approvals"].append(
                {
                    "id": key,
                    "status": "open",
                    "at": _now(),
                    "from": user.label,
                    "username": user.username,
                    "plant": user.plant,
                    "question": result.question.text,
                    "verdict": result.decision.verdict.value,
                    "result": json.loads(result.model_dump_json()),
                    "intent": json.loads(intent.model_dump_json()) if intent is not None else None,
                    "novice": bool(novice),
                }
            )
            return key

        return self._update(change)

    def is_waiting(self, username: str, result: StewardResult) -> bool:
        key = approval_key(username, result.question.text, result.decision.verdict.value)
        return any(a["id"] == key and a["status"] in ("open", "in_review") for a in self._read()["approvals"])

    def open_approvals(self) -> list[dict]:
        """Waiting for a builder, oldest first (light rows: no result payload)."""
        return [
            {k: v for k, v in a.items() if k not in ("result", "intent")}
            for a in self._read()["approvals"]
            if a["status"] == "open"
        ]

    def take(self, item_id: str, builder: str):
        """A builder opens a request: it leaves the open list. Returns (row, StewardResult, Intent | None)."""
        from .intent import Intent

        def change(data):
            for a in data["approvals"]:
                if a["id"] == item_id and a["status"] == "open":
                    a.update(status="in_review", reviewer=builder, reviewed_at=_now())
                    return a
            return None

        row = self._update(change)
        if row is None:
            return None
        intent = Intent.model_validate(row["intent"]) if row.get("intent") else None
        return row, StewardResult.model_validate(row["result"]), intent

    def decide(self, item_id: str, status: str, actor: str, reason: str = "", detail: str = "") -> None:
        """status 'approved' | 'sent_back'. The requester gets a notice with the outcome and the reason."""

        def change(data):
            for a in data["approvals"]:
                if a["id"] == item_id:
                    a.update(status=status, decided_by=actor, decided_at=_now(), reason=reason)
                    what = "approved" if status == "approved" else "sent back"
                    text = f'Your request "{a["question"]}" was {what} by {actor}.'
                    text += f" Reason: {reason}" if reason else ""
                    text += f" {detail}" if detail else ""
                    _notify(data, a["username"], text)

        self._update(change)

    def release(self, item_id: str) -> None:
        """A builder left a review without deciding: it goes back to the open list."""

        def change(data):
            for a in data["approvals"]:
                if a["id"] == item_id and a["status"] == "in_review":
                    a["status"] = "open"

        self._update(change)

    def release_reviews_of(self, builder: str) -> None:
        """Everything this builder left in review goes back to the open list (they hold no review right now)."""
        def change(data):
            for a in data["approvals"]:
                if a["status"] == "in_review" and a.get("reviewer") == builder:
                    a["status"] = "open"

        if any(a["status"] == "in_review" and a.get("reviewer") == builder for a in self._read()["approvals"]):
            self._update(change)

    # -- floor requests and grants -------------------------------------------------------------------------------
    def floor(self, status: str | None = "open") -> list[dict]:
        rows = self._read()["floor"]
        return [r for r in rows if status is None or r["status"] == status]

    def add_floor(self, entry: dict, same) -> tuple[dict, bool]:
        """Add a floor request, or join an identical open one (`same(open_rows, entry)` finds it). Returns
        (the stored row, joined)."""

        def change(data):
            existing = same([r for r in data["floor"] if r["status"] == "open"], entry)
            if existing:
                if entry["username"] != existing["username"] and entry["username"] not in existing.setdefault(
                    "also", []
                ):
                    existing["also"].append(entry["username"])
                return existing, True
            row = {
                **entry,
                "id": hashlib.sha256(f"{entry['username']}|{entry['need']}|{_now()}".encode()).hexdigest()[:12],
            }
            data["floor"].append(row)
            return row, False

        return self._update(change)

    def decide_floor(self, row_id: str, status: str, actor: str) -> dict | None:
        """status 'granted' | 'started' | 'declined'; everyone on the request gets a notice."""

        def change(data):
            for r in data["floor"]:
                if r.get("id") == row_id:
                    r.update(status=status, decided_by=actor, decided_at=_now())
                    if status == "granted":
                        depts = data["grants"].setdefault(r["username"], [])
                        if r["department"] not in depts:
                            depts.append(r["department"])
                    what = {
                        "granted": f"granted: {r.get('department')} data is now on your screen",
                        "started": "picked up: the BI team is building it",
                        "declined": "declined",
                    }.get(status, status)
                    for who in [r["username"], *r.get("also", [])]:
                        _notify(data, who, f'Your request "{r["need"]}" was {what} ({actor}).')
                    return r
            return None

        return self._update(change)

    def grants(self, username: str) -> list[str]:
        return list(self._read()["grants"].get(username, []))

    # -- notices -------------------------------------------------------------------------------------------------
    def pop_notices(self, username: str) -> list[str]:
        def change(data):
            return data["notices"].pop(username, [])

        return self._update(change)


def _notify(data: dict, username: str, text: str) -> None:
    data["notices"].setdefault(username, []).append(text)
