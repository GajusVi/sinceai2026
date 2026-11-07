"""Autofill from colleagues' requests (Gajus, Sun 8 Nov): the first message of an interview, remembered with the Intent
it ended in, offered back to people in the same role and plant.

- `record(user, text, intent)`: called when an interview ends in a decision. Refused, off-topic and CLARIFY requests
  are never stored. One entry per request text and audience (role, plant, and department for workers); the entry
  remembers WHO asked (distinct usernames), so popularity = people, not clicks.
- `for_user(user, typed)`: the suggestions this person may see, ranked by popularity (+ recency); with `typed`, only
  the ones whose words match it (token prefix + character trigrams: "xar ne" finds "Xarelto net sales ...").
- `intent_for(user, text)`: the confirmed Intent behind a picked suggestion. The app decides on it directly: no
  interview, no AI call (same request, same answer).

Who sees what: builders see every entry; managers their own plant's; workers their own plant AND department. A learned
request appears only once MIN_PEOPLE different people asked it, so one person's question never shows to colleagues.
The seed (Business_Requests of the data pack: real requests with their repeat counts, no role or plant) is visible to
managers and builders at every plant and carries no Intent: picking it starts the normal interview.

Memory, not demo state: both files live in `memory_dir()` (the user's app-data folder, or STEWARD_MEMORY_DIR), so they
survive app restarts and "Reset demo". Nothing is ever deleted (pruning junk is a later job):
- `suggestions.json`: the aggregated index the chips read (written atomically under a process lock, as inbox.py);
- `requests.jsonl`: EVERY first message with who asked, the path (interview, reused, expert) and the outcome (verdict,
  report, Intent), refused and off-topic ones included: the raw log for backtests (tools/backtest_requests.py).
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

FILE = "suggestions.json"
LOG = "requests.jsonl"
ENV_DIR = "STEWARD_MEMORY_DIR"
MIN_PEOPLE = 2  # privacy: a request shows to colleagues only after this many different people asked it
RECENT_DAYS = 7
_LOCK = threading.Lock()
_WORD = re.compile(r"[\w-]+", re.UNICODE)


@dataclass
class Suggestion:
    text: str
    people: int  # distinct people who asked it (seed: the data pack's repeat count)
    intent: dict | None = None  # the confirmed Intent (learned entries only)
    source: str = "colleagues"  # colleagues | requests (the data pack's Business_Requests)
    score: float = 0.0


def memory_dir() -> Path:
    """Where the autofill memory lives: STEWARD_MEMORY_DIR, else the per-user app-data folder (outlives the app's
    per-launch data copy). macOS ~/Library/Application Support/BI Steward/memory, Windows %APPDATA%/BI Steward/memory."""
    if os.environ.get(ENV_DIR):
        return Path(os.environ[ENV_DIR])
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "BI Steward" / "memory"


def norm(text: str) -> str:
    return " ".join(_WORD.findall(text.lower()))


def _trigrams(text: str) -> set[str]:
    t = f"  {norm(text)} "
    return {t[i : i + 3] for i in range(len(t) - 2)}


def match(typed: str, text: str) -> float:
    """0..1. Every typed word must start a word of the text ("xar ne" -> "Xarelto net"); trigrams break ties and
    forgive one typo. 0 = not a match."""
    words, target = norm(typed).split(), norm(text).split()
    if not words:
        return 1.0
    hits = sum(any(t.startswith(w) for t in target) for w in words)
    if hits < len(words) - (1 if len(words) >= 3 else 0):  # one miss allowed in a longer query (a typo)
        return 0.0
    a, b = _trigrams(typed), _trigrams(text)
    return 0.6 * hits / len(words) + 0.4 * (len(a & b) / len(a) if a else 0.0)


def _audience(user) -> dict:
    return {"role": user.role, "plant": user.plant, "department": user.department if user.role == "worker" else ""}


def visible(entry: dict, user) -> bool:
    if user.role == "builder":
        return True
    if entry.get("plant") == "*":  # the seed: company-wide commercial requests
        return user.role in ("management", "builder")
    a = _audience(user)
    return (
        entry["role"] == a["role"] and entry["plant"] == a["plant"] and entry.get("department", "") == a["department"]
    )


@lru_cache(maxsize=1)
def _pack_seed() -> list[tuple[str, int]]:
    """Business_Requests of the data pack: each distinct request text with how often it was asked."""
    try:
        from .requests import load_requests

        return sorted(Counter(r.text for r in load_requests()).items(), key=lambda x: -x[1])
    except Exception:  # noqa: BLE001 - no data pack: no seed, the learned entries still work
        return []


class Suggestions:
    def __init__(self, data_dir: Path | None = None, seed: list[tuple[str, int]] | None = None):
        base = Path(data_dir) if data_dir is not None else memory_dir()
        self.path, self.log_path = base / FILE, base / LOG
        self._seed = seed  # None = read the data pack's Business_Requests on first use

    # -- storage -------------------------------------------------------------------------------------------------
    def _read(self) -> list[dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        return data if isinstance(data, list) else []

    def _write(self, data: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, self.path)

    def seed(self) -> list[tuple[str, int]]:
        if self._seed is None:
            self._seed = _pack_seed()
        return self._seed

    # -- write -----------------------------------------------------------------------------------------------------
    def log(self, user, text: str, path: str, verdict: str, intent: dict | None = None, asset: str | None = None,
            **extra) -> None:
        """Append one first message and what came of it (any outcome) to requests.jsonl, for backtests."""
        if not text or not text.strip():
            return
        row = {"at": datetime.now().isoformat(timespec="seconds"), "user": user.username, **_audience(user),
               "text": text.strip(), "path": path, "verdict": verdict, "asset": asset, "intent": intent, **extra}
        with _LOCK:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, default=str) + "\n")

    def history(self) -> list[dict]:
        try:
            lines = self.log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in lines:
            try:
                out.append(json.loads(line))
            except ValueError:  # a half-written line from a crash: skip it, keep the rest
                continue
        return out

    def record(self, user, text: str, intent: dict) -> None:
        key = norm(text)
        if not key:
            return
        aud = _audience(user)
        with _LOCK:
            data = self._read()
            entry = next((e for e in data if e["key"] == key and all(e.get(k, "") == v for k, v in aud.items())), None)
            if entry is None:
                entry = {"key": key, "text": text.strip(), **aud, "users": [], "intent": intent}
                data.append(entry)
            if user.username not in entry["users"]:
                entry["users"].append(user.username)
            entry["intent"], entry["last"] = intent, datetime.now().isoformat(timespec="seconds")
            self._write(data)

    # -- read ------------------------------------------------------------------------------------------------------
    def for_user(self, user, typed: str = "", k: int = 4, seed: bool = True) -> list[Suggestion]:
        now, seen, out = datetime.now(), set(), []
        for e in self._read():
            if not visible(e, user) or len(e["users"]) < MIN_PEOPLE:
                continue
            m = match(typed, e["text"])
            if m <= 0:
                continue
            recent = (now - datetime.fromisoformat(e.get("last", "2000-01-01"))).days <= RECENT_DAYS
            pop = len(e["users"]) * (1.5 if recent else 1.0)
            out.append(Suggestion(e["text"], len(e["users"]), e.get("intent"), "colleagues", m * (1 + math.log1p(pop))))
            seen.add(e["key"])
        if seed and user.role in ("management", "builder"):
            for text, count in self.seed():
                m = match(typed, text)
                if m > 0 and norm(text) not in seen:
                    out.append(Suggestion(text, count, None, "requests", m * (1 + math.log1p(count)) * 0.8))
        out.sort(key=lambda s: -s.score)
        return out[:k]

    def intent_for(self, user, text: str) -> dict | None:
        """The Intent behind a learned request this user may see (None: not learned, not shared enough, not theirs)."""
        key = norm(text)
        for e in self._read():
            if e["key"] == key and visible(e, user) and len(e["users"]) >= MIN_PEOPLE and e.get("intent"):
                return e["intent"]
        return None
