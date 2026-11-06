import subprocess
import sys
from pathlib import Path

from tools import coord

ROOT = Path(__file__).resolve().parents[2]


def test_parse_fields():
    f = coord.parse("# x\nnow: L4 trust\nblocked: -\n")
    assert f["now"] == "L4 trust" and f["blocked"] == "-"


def test_brief_runs_offline():
    out = subprocess.run([sys.executable, str(ROOT / "tools" / "coord.py"), "brief", "--full", "--no-fetch"],
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0
    assert "TEAM BOARD" in out.stdout
    assert "None" not in out.stdout.splitlines()


def test_message_parse_split():
    head, _, body = "id: x\nfrom: margiris\nto: all\nkind: breaks\n---\nline1\nline2\n".partition("\n---\n")
    assert coord.parse(head)["kind"] == "breaks" and body.startswith("line1")


def test_discord_board_fits_one_message():
    text = coord.discord_board()
    assert text.startswith("**TEAM BOARD**") and len(text) <= 1990


def test_discord_noop_without_webhook(monkeypatch):
    monkeypatch.setattr(coord, "env_value", lambda key: "")
    coord.discord("feed line")  # must not raise or touch the network


def test_bad_webhook_value_does_not_crash():
    assert coord.discord_call("POST", 'echo "COORD_DISCORD_WEBHOOK=$(pbpaste)" >> .env', "x") is None
