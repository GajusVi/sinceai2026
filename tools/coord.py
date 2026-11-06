"""Team board for four Claude Code sessions, carried by git (no server).

coord/status/<name>.md  each person's Claude writes only its own file: now / done / next / blocked
coord/asks/<id>.md      one file per ask (needs an OK, a file edit, a decision); the recipient sets status

  python tools/coord.py brief [--full] [--no-fetch]    what the hooks print into Claude's context
  python tools/coord.py status --now "..." [--done ...] [--next ...] [--blocked ...]
  python tools/coord.py ask <name> "text" [--files a b]
  python tools/coord.py reply <ask-id> ok|no|done "text"   ONLY after your person said so in the chat
  python tools/coord.py say <name|all> "text" [--kind breaks|need|done|fyi|question] [--re <msg-id>]
                                                       free-form message to one teammate's Claude or everyone
  python tools/coord.py board                          full board for humans
coord/chat/<id>.md       one file per message (header + body); optional Discord mirror via COORD_DISCORD_WEBHOOK in .env
Teammates' updates are read from origin/main, so you see them before you pull.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEAM = ["gajus", "margiris", "martynas", "donatas"]
FETCH_EVERY_S = 120
SEEN = ROOT / ".git" / "coord_seen"
SEEN_MSGS = ROOT / ".git" / "coord_seen_msgs"
KINDS = ["breaks", "need", "done", "fyi", "question"]
SHOW_CHARS = 400


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


def messages() -> list[dict[str, str]]:
    names = set(git("ls-tree", "--name-only", "origin/main", "coord/chat/").splitlines())
    names |= {f"coord/chat/{p.name}" for p in (ROOT / "coord" / "chat").glob("*.md")}
    out = []
    for n in sorted(names):
        if not n.endswith(".md") or "README" in n:
            continue
        head, _, body = read_remote(n).partition("\n---\n")
        out.append(parse(head) | {"body": body.strip(), "file": n})
    return out


def seen_msgs() -> set[str]:
    return set(SEEN_MSGS.read_text().split()) if SEEN_MSGS.exists() else set()


def message_lines(who: str, full: bool) -> tuple[list[str], list[str]]:
    """Unseen messages for me or everyone (all recent ones when full). Returns (lines, ids shown)."""
    seen = seen_msgs()
    mine = [m for m in messages() if m.get("to") in (who, "all") and m.get("from") != who]
    show = mine[-10:] if full else [m for m in mine if m.get("id") not in seen][-8:]
    lines = []
    for m in show:
        tag = "MESSAGE FOR YOU" if m.get("to") == who else "message to all"
        body = m["body"] if len(m["body"]) <= SHOW_CHARS else m["body"][:SHOW_CHARS] + f"... (full: {m['file']})"
        re_ = f" re {m['re']}" if m.get("re") else ""
        lines.append(f"- {tag} [{m.get('kind', 'fyi').upper()}] {m.get('id')} from {m.get('from')}{re_}: {body}")
    return lines, [m.get("id", "") for m in show]


def board_text(who: str, full: bool = True) -> str:
    lines = ["TEAM BOARD (tools/coord.py; teammates' state from origin/main)"]
    for person in TEAM:
        s = parse(read_remote(f"coord/status/{person}.md"))
        if s:
            mark = " (you)" if person == who else ""
            lines.append(
                f"- {person}{mark} [{s.get('updated', '?')}] now: {s.get('now', '-')} | next: {s.get('next', '-')}"
                + (f" | BLOCKED: {s['blocked']}" if s.get("blocked", "-") not in ("", "-") else "")
            )
    open_asks = [a for a in asks() if a.get("status") == "open"]
    for a in open_asks:
        tag = "ASK FOR YOU" if a.get("to") == who else "open ask"
        lines.append(
            f"- {tag} {a.get('id')}: {a.get('from')} -> {a.get('to')}: {a.get('ask')}"
            + (f" (files: {a['files']})" if a.get("files") else "")
        )
    for a in asks():
        if a.get("from") == who and a.get("status") in ("ok", "no", "done") and a.get("seen_by_sender") != "yes":
            lines.append(f"- ANSWER TO YOUR ASK {a.get('id')}: {a.get('status').upper()} {a.get('reply', '')}")
    msg_lines, _ = message_lines(who, full)
    lines += msg_lines
    behind = git("rev-list", "--count", "HEAD..origin/main") or "0"
    if behind != "0":
        lines.append(
            f"- You are {behind} commits behind origin/main: run `git pull --rebase --autostash` before editing."
        )
        lines += ["  " + c for c in git("log", "--format=%h %an: %s", "-n", "6", "HEAD..origin/main").splitlines()]
    return "\n".join(lines)


def cmd_brief(full: bool, no_fetch: bool) -> None:
    if not no_fetch:
        fetch()
    who = me()
    text = board_text(who, full)
    _, shown = message_lines(who, full)
    digest = hashlib.sha1(text.encode()).hexdigest()
    urgent = any(
        t in text for t in ("ASK FOR YOU", "ANSWER TO YOUR ASK", "commits behind", "MESSAGE FOR YOU", "message to all")
    )
    changed = not SEEN.exists() or SEEN.read_text() != digest
    if full or changed or urgent:
        print(text)
        print("Protocol: CLAUDE.md 'Team board'. Answer asks only with your person's explicit yes/no.")
        SEEN.write_text(digest)
        if shown:
            SEEN_MSGS.write_text(" ".join(sorted(seen_msgs() | set(shown))))


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
    body = (
        f"id: {ask_id}\nfrom: {who}\nto: {to}\nstatus: open\ncreated: {now()}\nask: {a.text}\n"
        f"files: {' '.join(a.files or [])}\nreply: \nreplied: \n"
    )
    path = ROOT / "coord" / "asks" / f"{ask_id}.md"
    path.write_text(body, encoding="utf-8")
    write_and_sync(path, f"coord({who}): ask {to}: {a.text[:50]}")
    discord(f"**{who} asks {to}** ({ask_id}): {a.text}")


def discord(text: str) -> None:
    """Optional human mirror: COORD_DISCORD_WEBHOOK=<url> in .env (never committed)."""
    env = ROOT / ".env"
    url = ""
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("COORD_DISCORD_WEBHOOK="):
                url = line.split("=", 1)[1].split("#")[0].strip()
    if not url:
        return
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"content": text[:1900]}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": "coord-board"},
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # the git copy is the source of truth


def cmd_say(a: argparse.Namespace) -> None:
    who, to = me(), a.to.lower()
    if to not in TEAM + ["all"]:
        sys.exit(f"unknown recipient {to!r}; one of {TEAM + ['all']}")
    msg_id = f"{datetime.now():%m%d-%H%M%S}-{who}-to-{to}"
    head = f"id: {msg_id}\nfrom: {who}\nto: {to}\nkind: {a.kind}\ncreated: {now()}\nre: {a.re or ''}\n"
    path = ROOT / "coord" / "chat" / f"{msg_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(head + "---\n" + a.text.strip() + "\n", encoding="utf-8")
    write_and_sync(path, f"coord({who}) {a.kind} -> {to}: {a.text.strip().splitlines()[0][:60]}")
    discord(f"**{who} -> {to}** [{a.kind}] {a.text.strip()}")


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
    y = sub.add_parser("say")
    y.add_argument("to")
    y.add_argument("text")
    y.add_argument("--kind", choices=KINDS, default="fyi")
    y.add_argument("--re")
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
        {"status": cmd_status, "ask": cmd_ask, "reply": cmd_reply, "say": cmd_say}[a.cmd](a)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(f"git step failed ({e.cmd[1]}): resolve, then rerun")
