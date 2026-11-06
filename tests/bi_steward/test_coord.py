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
