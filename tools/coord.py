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
import os
import subprocess
import sys
import time
import urllib.error
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
        # utf-8 explicitly: Windows defaults to cp1252 and crashed on an emoji in a message
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=timeout)
        return (out.stdout or "").strip() if out.returncode == 0 else ""
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


def read_many(paths: list[str]) -> dict[str, str]:
    """read_remote for many files in ONE git call (one git process per file took 30 s on Windows)."""
    got: dict[str, str] = {}
    try:
        req = "".join(f"origin/main:{p}\n" for p in paths).encode("utf-8")
        raw = subprocess.run(["git", "cat-file", "--batch"], cwd=ROOT, input=req,
                             capture_output=True, timeout=20).stdout
        for p in paths:
            header, _, raw = raw.partition(b"\n")
            if not header or header.endswith(b" missing"):
                continue
            size = int(header.split()[-1])
            got[p] = raw[:size].decode("utf-8", "replace").strip()
            raw = raw[size + 1:]
    except (subprocess.SubprocessError, OSError, ValueError):
        got = {}
    for p in paths:
        if not got.get(p):
            got[p] = (ROOT / p).read_text(encoding="utf-8").strip() if (ROOT / p).exists() else ""
    return got


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
    names = sorted(n for n in names if n.endswith(".md") and "README" not in n)
    texts = read_many(names)
    return [parse(texts[n]) | {"file": n} for n in names]


def messages() -> list[dict[str, str]]:
    names = set(git("ls-tree", "--name-only", "origin/main", "coord/chat/").splitlines())
    names |= {f"coord/chat/{p.name}" for p in (ROOT / "coord" / "chat").glob("*.md")}
    names = sorted(n for n in names if n.endswith(".md") and "README" not in n)
    texts = read_many(names)
    out = []
    for n in names:
        head, _, body = texts[n].partition("\n---\n")
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


def cmd_mirror(before: str, after: str) -> None:
    """GitHub workflow: post every new message / ask / answer between two commits, then refresh the live board."""
    if not env_value("COORD_DISCORD_WEBHOOK"):
        print("coord mirror: repo secret COORD_DISCORD_WEBHOOK is not set yet, nothing posted")
        return
    if not before or set(before) == {"0"}:
        before = f"{after}~1"
    feed = []
    for line in git("diff", "--name-status", before, after, "--", "coord/").splitlines():
        parts = line.split("\t")
        state, path = parts[0], parts[-1]
        if not path.endswith(".md") or "README" in path:
            continue
        text = git("show", f"{after}:{path}")
        if path.startswith("coord/chat/") and state.startswith("A"):
            head, _, body = text.partition("\n---\n")
            m = parse(head)
            footer = m.get("id", "") + (f"  ·  re {m['re']}" if m.get("re") else "")
            feed.append(card(m.get("kind", "fyi"), m.get("from", "?"), m.get("to", "?"), body, footer))
        elif path.startswith("coord/asks/"):
            q = parse(text)
            if state.startswith("A"):
                files = f"\n**files:** {q['files']}" if q.get("files") else ""
                feed.append(
                    card("ask", q.get("from", "?"), q.get("to", "?"), q.get("ask", "") + files, q.get("id", ""))
                )
            elif q.get("status") in ("ok", "no", "done"):
                who = q.get("replied", "").split(" ")[0] or q.get("to", "?")
                kind = {"ok": "ok", "no": "no"}.get(q["status"], "answered")
                feed.append(card(kind, who, q.get("from", "?"), q.get("reply", ""), q.get("id", "")))
    for item in feed:
        discord_call("POST", env_value("COORD_DISCORD_WEBHOOK"), item)
    discord(force=True)
    print(f"coord mirror: {len(feed)} post(s), board refreshed")
    if FAILURES:
        sys.exit(f"coord mirror: Discord refused {len(FAILURES)} call(s): {', '.join(FAILURES)}")


def cmd_status(a: argparse.Namespace) -> None:
    who = me()
    path = ROOT / "coord" / "status" / f"{who}.md"
    old = parse(path.read_text(encoding="utf-8")) if path.exists() else {}
    fields = {k: getattr(a, k) or old.get(k, "-") for k in ("now", "done", "next", "blocked")}
    body = f"# {who}\nupdated: {now()}\n" + "".join(f"{k}: {v}\n" for k, v in fields.items())
    path.write_text(body, encoding="utf-8")
    write_and_sync(path, f"coord({who}): {fields['now'][:60]}")
    discord()  # status changes only refresh the live board, no feed line


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
    discord(card("ask", who, to, a.text + (f"\n**files:** {' '.join(a.files)}" if a.files else ""), ask_id))


DISCORD_STATE = ROOT / "coord" / "discord.json"  # shared id of the live board message


WORKFLOW = ROOT / ".github" / "workflows" / "coord-discord.yml"


def env_value(key: str) -> str:
    if os.environ.get(key):
        return os.environ[key].strip()
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].split("#")[0].strip()
    return ""


WEBHOOK_PREFIXES = ("https://discord.com/api/webhooks/", "https://discordapp.com/api/webhooks/")


FAILURES: list[str] = []
STYLE = {  # Discord embed colour + label per kind, so each post type is recognisable at a glance
    "breaks": (0xE5484D, "🔴 BREAKS"),
    "need": (0xF5A524, "🟠 NEED"),
    "done": (0x30A46C, "🟢 DONE"),
    "fyi": (0x8B8D98, "⚪ FYI"),
    "question": (0x8E4EC6, "🟣 QUESTION"),
    "escalate": (0x8E4EC6, "🟣 ESCALATE"),
    "ask": (0x3E63DD, "🔵 ASK"),
    "ok": (0x12A594, "✅ ANSWER: OK"),
    "no": (0xE5484D, "⛔ ANSWER: NO"),
    "answered": (0x30A46C, "☑️ ANSWER: DONE"),
}


def card(kind: str, who: str, to: str, body: str, footer: str = "") -> dict:
    """One feed post as a coloured Discord embed: '🔴 BREAKS · margiris → martynas' + body + id footer."""
    if kind == "question" and body.lstrip().upper().startswith("ESCALATE"):
        kind = "escalate"
    colour, label = STYLE.get(kind, STYLE["fyi"])
    embed = {"title": f"{label} · {who} → {to}", "description": body.strip()[:3900], "color": colour}
    if footer:
        embed["footer"] = {"text": footer[:200]}
    return {"embeds": [embed]}


def discord_call(method: str, url: str, payload: str | dict) -> dict | None:
    if not url.startswith(WEBHOOK_PREFIXES):
        print("coord: COORD_DISCORD_WEBHOOK is not a Discord webhook URL; run `make set-webhook`", file=sys.stderr)
        FAILURES.append("not a webhook URL")
        return None
    body = {"content": payload[:1990]} if isinstance(payload, str) else dict(payload)
    body["allowed_mentions"] = {"parse": []}
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode(),
            method=method,
            headers={"Content-Type": "application/json", "User-Agent": "DiscordBot (sinceai2026 coord, 1.0)"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        hint = " (webhook deleted or URL changed: update the secret / make set-webhook)" if e.code in (401, 404) else ""
        print(f"coord: Discord refused {method}: HTTP {e.code}{hint}", file=sys.stderr)
        FAILURES.append(f"{method} HTTP {e.code}")
    except Exception as e:  # network
        print(f"coord: Discord unreachable ({type(e).__name__})", file=sys.stderr)
        FAILURES.append(type(e).__name__)
    return None


def clipboard() -> str:
    for cmd in (
        ["pbpaste"],
        ["powershell", "-NoProfile", "-Command", "Get-Clipboard"],
        ["xclip", "-o", "-selection", "clipboard"],
    ):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if out.returncode == 0:
                return out.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            continue
    return ""


def cmd_set_webhook() -> None:
    """Write the webhook URL from the clipboard into .env (replacing any old COORD_DISCORD_WEBHOOK line)."""
    url = clipboard()
    if not url.startswith(WEBHOOK_PREFIXES):
        sys.exit(
            "Clipboard does not hold a Discord webhook URL. In Discord: #llm-board settings > Integrations > Webhooks >"
            " LLM Board > Copy Webhook URL. Then TYPE `make set-webhook` (copying the command would replace the URL)."
        )
    env = ROOT / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    lines = [ln for ln in lines if not ln.startswith("COORD_DISCORD_WEBHOOK=")] + [f"COORD_DISCORD_WEBHOOK={url}"]
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("COORD_DISCORD_WEBHOOK set in .env (old line replaced). Next: make board-discord (first person only).")


def discord_board() -> str:
    """Neutral view of the board for the Discord channel (fits one 2,000-character message)."""
    lines = [f"📋 **TEAM BOARD**  ·  live  ·  updated {now()}", "```"]
    for person in TEAM:
        s = parse(read_remote(f"coord/status/{person}.md"))
        if s:
            blocked = s.get("blocked", "-")
            lines.append(f"{person:<9} {s.get('updated', '?')[-5:]}  now: {s.get('now', '-')[:70]}")
            lines.append(
                f"{'':<16}next: {s.get('next', '-')[:70]}"
                + (f"  BLOCKED: {blocked[:40]}" if blocked not in ("", "-") else "")
            )
    open_asks = [a for a in asks() if a.get("status") == "open"]
    lines.append("")
    lines.append(f"OPEN ASKS ({len(open_asks)})")
    lines += [f"  {a.get('from')} -> {a.get('to')}: {a.get('ask', '')[:80]}" for a in open_asks[-6:]] or ["  none"]
    lines.append("")
    lines.append("LAST MESSAGES")
    msgs = messages()[-5:]
    lines += [
        f"  [{m.get('kind', 'fyi')}] {m.get('from')} -> {m.get('to')}: {m['body'].splitlines()[0][:80]}" for m in msgs
    ] or ["  none"]
    lines.append("")
    lines.append("LAST COMMITS (origin/main)")
    lines += ["  " + c[:95] for c in git("log", "--format=%h %an: %s", "-n", "5", "origin/main").splitlines()]
    lines.append("```")
    return "\n".join(lines)[:1990]


def discord(feed: str | dict | None = None, force: bool = False) -> None:
    """Post one feed line (if any) and refresh the pinned live board.
    When the GitHub workflow exists, GitHub mirrors every push for everyone, so laptops stay quiet (no duplicates);
    `force` (make board-discord) still works locally, e.g. to create the board the first time."""
    if WORKFLOW.exists() and not force and not os.environ.get("GITHUB_ACTIONS"):
        return
    url = env_value("COORD_DISCORD_WEBHOOK")
    if not url:
        return
    if feed:
        discord_call("POST", url, feed)
    state = json.loads(read_remote("coord/discord.json") or "{}")
    board_id = state.get("board_message_id")
    if board_id and discord_call("PATCH", f"{url}/messages/{board_id}", discord_board()) is not None:
        return
    if os.environ.get("GITHUB_ACTIONS"):
        print("coord: no live board message yet; run `make board-discord` once on a laptop and pin it")
        return
    created = discord_call("POST", f"{url}?wait=true", discord_board())
    if created and created.get("id"):
        DISCORD_STATE.write_text(json.dumps({"board_message_id": created["id"]}) + "\n", encoding="utf-8")
        write_and_sync(DISCORD_STATE, "coord: new live board message in Discord (pin it)")


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
    discord(card(a.kind, who, to, a.text, msg_id + (f"  ·  re {a.re}" if a.re else "")))


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
    discord(card({"ok": "ok", "no": "no"}.get(a.verdict, "answered"), who, fields.get("from", "?"), a.text, a.ask_id))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("brief")
    b.add_argument("--full", action="store_true")
    b.add_argument("--no-fetch", action="store_true")
    sub.add_parser("board")
    sub.add_parser("discord")
    sub.add_parser("set-webhook")
    mi = sub.add_parser("mirror")
    mi.add_argument("before")
    mi.add_argument("after")
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
    elif a.cmd == "mirror":
        cmd_mirror(a.before, a.after)
    elif a.cmd == "set-webhook":
        cmd_set_webhook()
    elif a.cmd == "discord":
        fetch(force=True)
        if not env_value("COORD_DISCORD_WEBHOOK"):
            sys.exit("Set COORD_DISCORD_WEBHOOK=<webhook url> in .env first")
        discord(force=True)
        if FAILURES:
            sys.exit(f"Discord refused: {', '.join(FAILURES)}. Check COORD_DISCORD_WEBHOOK (make set-webhook).")
        print("Discord board refreshed (pin the TEAM BOARD message once)")
    elif a.cmd == "board":
        fetch(force=True)
        print(board_text(me()))
    else:
        {"status": cmd_status, "ask": cmd_ask, "reply": cmd_reply, "say": cmd_say}[a.cmd](a)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # cp1252 consoles cannot print emoji
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    try:
        main()
    except subprocess.CalledProcessError as e:
        sys.exit(f"git step failed ({e.cmd[1]}): resolve, then rerun")
