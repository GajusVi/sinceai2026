"""Audit trail in SQLite: every model output and every human decision, with time and input."""

import csv
import io
import json
import sqlite3
import threading
from datetime import datetime, timezone

from .config import get_settings

_lock = threading.Lock()
SCHEMA = """
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    event TEXT NOT NULL,           -- 'decision' | 'review'
    item_id TEXT NOT NULL,
    input TEXT,
    output TEXT,
    source TEXT,
    verdict TEXT,
    note TEXT,
    reviewer TEXT
);
"""


def _conn() -> sqlite3.Connection:
    path = get_settings().db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    return c


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_decision(scored) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO audit (ts, event, item_id, input, output, source) VALUES (?,?,?,?,?,?)",
            (_now(), "decision", scored.item.id, scored.item.text, scored.decision.model_dump_json(), scored.source),
        )


def log_review(review) -> None:
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO audit (ts, event, item_id, verdict, note, reviewer) VALUES (?,?,?,?,?,?)",
            (_now(), "review", review.item_id, review.verdict, review.note, review.reviewer),
        )


def fetch(limit: int = 500) -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def latest_verdicts() -> dict[str, str]:
    with _conn() as c:
        rows = c.execute("SELECT item_id, verdict FROM audit WHERE event='review' ORDER BY id").fetchall()
    return {r["item_id"]: r["verdict"] for r in rows}


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    if rows:
        w = csv.DictWriter(buf, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return buf.getvalue()


def reset() -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM audit")


if __name__ == "__main__":
    print(json.dumps(fetch(20), indent=2))
