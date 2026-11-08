"""Build the BI Steward desktop app with PyInstaller (DECISION T2.6).

    make app-setup && .venv/bin/python tools/build_app.py        # macOS -> dist/BI Steward.app
    .\\run.ps1 app-setup; .venv\\Scripts\\python.exe tools\\build_app.py   # Windows -> dist\\BI Steward\\BI Steward.exe

Build on the platform you ship to (PyInstaller does not cross-compile). The bundle carries code + data, never .env:
a packaged app runs with the LLM off (rules + templates, stage-safe) unless the user sets a key in the environment.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "BI Steward"
SEP = os.pathsep  # PyInstaller --add-data "src{SEP}dest"

# (source, destination inside the bundle). Everything the Streamlit script and the engine read at runtime.
DATA = [
    ("frontend", "frontend"),  # steward_app.py, ui.py, worker_view.py, steward.css, static/fonts
    ("app/shell", "app/shell"),  # native login + loading page (Donatas), vendor/ included
    (".streamlit", ".streamlit"),  # theme, fonts, static serving
    ("catalog", "catalog"),  # metrics.json, dimensions.json, measures.json
    ("data/bayer", "data/bayer"),  # the data pack .xlsx
    ("demo/steward_seed", "demo/steward_seed"),
    ("demo/cache", "demo/cache"),  # recorded LLM answers (DEMO_MODE replay)
    ("prompts", "prompts"),
    ("templates/pbip", "templates/pbip"),
    ("steward/layout_cache", "layout_cache"),  # NOT under steward/: a data folder there shadows the package
    ("THIRD_PARTY_NOTICES.md", "."),
]
HIDDEN = ["backend.llm", "backend.config", "ui", "worker_view", "org_panel"]


def _modules(package: str) -> list[str]:
    """Every module of a package of ours: the Streamlit script imports them at runtime, which PyInstaller's static
    analysis of app/main.py never sees (steward.render, steward.pbip, ... were missing from the first build)."""
    base = ROOT / package
    return sorted(
        ".".join(f.relative_to(ROOT).with_suffix("").parts).removesuffix(".__init__")
        for f in base.rglob("*.py")
        if "__pycache__" not in f.parts
    )


COLLECT = ["streamlit", "plotly", "pydantic", "pandas", "openpyxl", "streamlit_searchbox"]  # not our packages: their data would shadow them
METADATA = ["streamlit", "plotly", "pandas", "pydantic", "openpyxl", "numpy"]


def main() -> None:
    import PyInstaller.__main__

    args = [
        str(ROOT / "app" / "main.py"),
        "--name",
        NAME,
        "--noconfirm",
        "--clean",
        "--windowed",  # a GUI app: no terminal window
        "--onedir",  # a folder bundle starts fast; onefile unpacks 300 MB on every launch
        "--paths",
        str(ROOT),
        "--paths",
        str(ROOT / "frontend"),
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build" / "pyinstaller"),
        "--specpath",
        str(ROOT / "build"),
    ]
    if sys.platform == "darwin":
        args += ["--osx-bundle-identifier", "ai.sinceai.bisteward"]
    for src, dest in DATA:
        if (ROOT / src).exists():
            args += ["--add-data", f"{ROOT / src}{SEP}{dest}"]
    for name in HIDDEN + _modules("steward"):
        args += ["--hidden-import", name]
    for name in COLLECT:
        args += ["--collect-all", name]
    for name in METADATA:
        args += ["--copy-metadata", name]
    shutil.rmtree(ROOT / "build" / "pyinstaller", ignore_errors=True)
    PyInstaller.__main__.run(args)
    print(f"\nBuilt: {ROOT / 'dist' / (NAME + ('.app' if sys.platform == 'darwin' else ''))}")


if __name__ == "__main__":
    main()
