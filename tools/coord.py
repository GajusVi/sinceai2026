"""Team board for four Claude Code sessions, carried by git (no server).

coord/status/<name>.md  each person's Claude writes only its own file: now / done / next / blocked
coord/asks/<id>.md      one file per ask (needs an OK, a file edit, a decision); the recipient sets status

  python tools/coord.py brief [--full] [--no-fetch]    what the hooks print into Claude's context
  python tools/coord.py status --now "..." [--done ...] [--next ...] [--blocked ...]
  python tools/coord.py ask <name> "text" [--files a b]
  python tools/coord.py reply <ask-id> ok|no|done "text"   ONLY after your person said so in the chat
  python tools/coord.py board                          full board for humans
Teammates' updates are read from origin/main, so you see them before you pull.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEAM = ["gajus", "margiris", "martynas", "donatas"]
FETCH_EVERY_S = 120
SEEN = ROOT / ".git" / "coord_seen"


def git(*args: str, timeout: float = 10) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def me() -> str:
    name = git("config", "user.name").split()
    return name[0].lower() if name else "unknown"


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def fetch(force: bool = False) -> None:
    stamp = ROOT / ".git" / "coord_fetch"
    if not force and stamp.exists() and time.time() - stamp.stat().st_mtime < FETCH_EVERY_S:
        return
    git("fetch", "-q", "origin", timeout=8)
    stamp.touch()


def read_remote(path: str) -> str:
    """Prefer origin/main (teammates' latest), fall back to the working tree."""
    text = git("show", f"origin/main:{path}")
    if not text and (ROOT / path).exists():
        text = (ROOT / path).read_text(encoding="utf-8")
    return text


def parse(text: str) -> dict[str, str]:
    fields = {}
    for line in text.splitlines():
        if ":" in line and not line.startswith("#"):
            key, _, value = line.partition(":")
            fields[key.strip().lower()] = value.strip()
    return fields


def asks() -> list[dict[str, str]]:
    names = set(git("ls-tree", "--name-only", "origin/main", "coord/asks/").splitlines())
    names |= {f"coord/asks/{p.name}" for p in (ROOT / "coord" / "asks").glob("*.md")}
    return [parse(read_remote(n)) | {"file": n} for n in sorted(names) if n.endswith(".md") and "README" not in n]


def board_text(who: str) -> str:
    lines = ["TEAM BOARD (tools/coord.py; teammates' state from origin/main)"]
    for person in TEAM:
        s = parse(read_remote(f"coord/status/{person}.md"))
        if s:
            mark = " (you)" if person == who else ""
            lines.append(f"- {person}{mark} [{s.get('updated', '?')}] now: {s.get('now', '-')} | next: {s.get('next', '-')}"
                         + (f" | BLOCKED: {s['blocked']}" if s.get("blocked", "-") not in ("", "-") else ""))
    open_asks = [a for a in asks() if a.get("status") == "open"]
    for a in open_asks:
        tag = "ASK FOR YOU" if a.get("to") == who else "open ask"
        lines.append(f"- {tag} {a.get('id')}: {a.get('from')} -> {a.get('to')}: {a.get('ask')}"
                     + (f" (files: {a['files']})" if a.get("files") else ""))
    for a in asks():
        if a.get("from") == who and a.get("status") in ("ok", "no", "done") and a.get("seen_by_sender") != "yes":
            lines.append(f"- ANSWER TO YOUR ASK {a.get('id')}: {a.get('status').upper()} {a.get('reply', '')}")
    behind = git("rev-list", "--count", "HEAD..origin/main") or "0"
    if behind != "0":
        lines.append(f"- You are {behind} commits behind origin/main: run `git pull --rebase --autostash` before editing.")
        lines += ["  " + c for c in git("log", "--format=%h %an: %s", "-n", "6", "HEAD..origin/main").splitlines()]
    return "\n".join(lines)


def cmd_brief(full: bool, no_fetch: bool) -> None:
    if not no_fetch:
        fetch()
    who = me()
    text = board_text(who)
    digest = hashlib.sha1(text.encode()).hexdigest()
    urgent = "ASK FOR YOU" in text or "ANSWER TO YOUR ASK" in text or "commits behind" in text
    changed = not SEEN.exists() or SEEN.read_text() != digest
    if full or changed or urgent:
        print(text)
        print("Protocol: CLAUDE.md 'Team board'. Never reply ok/no to an ask without your person's explicit answer in this chat.")
        SEEN.write_text(digest)


def write_and_sync(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rel = str(path.relative_to(ROOT))
    subprocess.run(["git", "add", rel], cwd=ROOT, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message, "--", rel], cwd=ROOT, check=True)
    subprocess.run(["git", "pull", "-q", "--rebase", "--autostash"], cwd=ROOT, check=True)
    subprocess.run(["git", "push", "-q"], cwd=ROOT, check=True)
    print(f"pushed {rel}")


def cmd_status(a: argparse.Namespace) -> None:
    who = me()
    path = ROOT / "coord" / "status" / f"{who}.md"
    old = parse(path.read_text(encoding="utf-8")) if path.exists() else {}
    fields = {k: getattr(a, k) or old.get(k, "-") for k in ("now", "done", "next", "blocked")}
    body = f"# {who}\nupdated: {now()}\n" + "".join(f"{k}: {v}\n" for k, v in fields.items())
    path.write_text(body, encoding="utf-8")
    write_and_sync(path, f"coord({who}): {fields['now'][:60]}")


def cmd_ask(a: argparse.Namespace) -> None:
    who, to = me(), a.to.lower()
    if to not in TEAM:
        sys.exit(f"unknown teammate {to!r}; one of {TEAM}")
    ask_id = f"{datetime.now():%m%d-%H%M%S}-{who}-to-{to}"
    body = (f"id: {ask_id}\nfrom: {who}\nto: {to}\nstatus: open\ncreated: {now()}\nask: {a.text}\n"
            f"files: {' '.join(a.files or [])}\nreply: \nreplied: \n")
    path = ROOT / "coord" / "asks" / f"{ask_id}.md"
    path.write_text(body, encoding="utf-8")
    write_and_sync(path, f"coord({who}): ask {to}: {a.text[:50]}")


def cmd_reply(a: argparse.Namespace) -> None:
    who = me()
    git("pull", "-q", "--rebase", "--autostash", timeout=30)
    path = ROOT / "coord" / "asks" / f"{a.ask_id}.md"
    if not path.exists():
        sys.exit(f"no ask {a.ask_id}")
    fields = parse(path.read_text(encoding="utf-8"))
    if who not in (fields.get("to"), fields.get("from")):
        sys.exit(f"{who} is neither sender nor recipient of {a.ask_id}")
    fields.update({"status": a.verdict, "reply": a.text, "replied": f"{who} {now()}"})
    if who == fields.get("from"):
        fields["seen_by_sender"] = "yes"
    path.write_text("".join(f"{k}: {v}\n" for k, v in fields.items()), encoding="utf-8")
    write_and_sync(path, f"coord({who}): {a.verdict} on {a.ask_id}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("brief")
    b.add_argument("--full", action="store_true")
    b.add_argument("--no-fetch", action="store_true")
    sub.add_parser("board")
    s = sub.add_parser("status")
    for k in ("now", "done", "next", "blocked"):
        s.add_argument(f"--{k}")
    k = sub.add_parser("ask")
    k.add_argument("to")
    k.add_argument("text")
    k.add_argument("--files", nargs="*")
    r = sub.add_parser("reply")
    r.add_argument("ask_id")
    r.add_argument("verdict", choices=["ok", "no", "done"])
    r.add_argument("text")
    a = p.parse_args()
    if a.cmd == "brief":
        cmd_brief(a.full, a.no_fetch)
    elif a.cmd == "board":
        fetch(force=True)
        print(board_text(me()))
    else:
        {"status": cmd_status, "ask": cmd_ask, "reply": cmd_reply}[a.cmd](a)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(f"git step failed ({e.cmd[1]}): resolve, then rerun")
