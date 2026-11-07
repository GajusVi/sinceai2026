"""BI Steward desktop app (DECISION T2.6): a native window, not a browser page.

1. A small native window opens on the login page (app/shell/login.html, served locally).
2. The password is checked here in Python (steward/auth.py); the page shows the loading screen.
3. When the engine is up, the same window grows into the workspace (the Streamlit app, without browser or Streamlit
   chrome), signed in by a short-lived token (steward/apptoken.py). "Log out" brings the window back to the login.

Run: `make app` (from the repo) or the packaged BI Steward.app / .exe (tools/build_app.py).
Data: STEWARD_DATA_DIR if set, else a fresh copy of demo/steward_seed per run (stage-safe, like `make demo`).
"""

from __future__ import annotations

import multiprocessing
import os
import secrets
import shutil
import socket
import sys
import tempfile
import threading
import time
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(ROOT))  # `steward` is importable from the repo and from the frozen app
LOGIN_SIZE = (440, 600)
WORKSPACE_SIZE = (1360, 860)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _serve_shell(port: int) -> None:
    """The login page and its fonts, from the app folder, on localhost only."""
    handler = partial(_QuietHandler, directory=str(ROOT))
    ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # no request log in the terminal
        pass


def _run_streamlit(port: int, env: dict[str, str]) -> None:
    """Child process: the Streamlit server for the workspace (its main thread is free for signals)."""
    os.environ.update(env)
    os.chdir(ROOT)  # .streamlit/config.toml (theme, fonts, static serving) is read from here
    from streamlit import config as st_config
    from streamlit.web import bootstrap

    script = str(ROOT / "frontend" / "steward_app.py")
    st_config._main_script_path = script  # as `streamlit run` does: config and static files resolve from here
    flags = {  # bootstrap.run takes the CLI's underscore names ("server.port" is silently ignored)
        "server_port": port,
        "server_address": "127.0.0.1",
        "server_headless": True,
        "server_runOnSave": False,
        "server_fileWatcherType": "none",
        "browser_gatherUsageStats": False,
        "global_developmentMode": False,
    }
    bootstrap.load_config_options(flag_options=flags)  # without this, run() ignores the port and listens on all hosts
    bootstrap.run(script, False, [], flags)


def _data_dir() -> str:
    if os.environ.get("STEWARD_DATA_DIR"):
        return os.environ["STEWARD_DATA_DIR"]
    target = Path(tempfile.mkdtemp(prefix="bi-steward-"))
    seed = ROOT / "demo" / "steward_seed"
    if seed.is_dir():
        shutil.copytree(seed, target, dirs_exist_ok=True)
    return str(target)


class Api:
    """Called from the login page as window.pywebview.api.<name>(...)."""

    def __init__(self, app_port: int, secret: str):
        self._port, self._secret = app_port, secret  # private: never visible to the page
        self._user = None
        self._window = None  # private: pywebview exposes public attributes to JavaScript

    def accounts(self) -> list[dict]:
        from steward.auth import DEMO_ACCOUNTS

        return [{"username": n, "password": p, "role": r} for n, p, r in DEMO_ACCOUNTS]

    def login(self, username: str, password: str) -> dict:
        from steward.auth import login

        user = login(username or "", password or "")
        if user is None:
            return {"ok": False, "error": "Wrong username or password."}
        self._user = user
        plant = "all plants" if user.role == "builder" else user.plant
        return {"ok": True, "username": user.username, "role": user.role.capitalize(), "plant": plant}

    def ready(self) -> bool:
        """True once the workspace server answers (the loading screen polls this)."""
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self._port}/_stcore/health", timeout=1) as r:
                return r.status == 200
        except OSError:
            return False

    def open(self) -> None:
        """Grow the window into the workspace and sign the user in there."""
        from steward.apptoken import sign

        if self._user is None or self._window is None:
            return
        url = f"http://127.0.0.1:{self._port}/?u={self._user.username}&t={sign(self._user.username, self._secret)}"

        def go() -> None:  # after this call has answered the page: navigating first would orphan its reply
            time.sleep(0.15)
            self._window.resize(*WORKSPACE_SIZE)
            self._window.load_url(url)

        threading.Thread(target=go, daemon=True).start()

    def compact(self) -> None:
        """Back to the small login window (the login page calls this when it loads)."""
        self._user = None
        if self._window is not None:
            self._window.resize(*LOGIN_SIZE)


def main() -> None:
    import webview

    shell_port, app_port, secret = _free_port(), _free_port(), secrets.token_hex(16)
    login_url = f"http://127.0.0.1:{shell_port}/app/shell/login.html"
    threading.Thread(target=_serve_shell, args=(shell_port,), daemon=True).start()

    env = {
        "STEWARD_APP_SECRET": secret,
        "STEWARD_APP_LOGIN_URL": login_url,
        "STEWARD_DATA_DIR": _data_dir(),
        "STEWARD_CATALOG": os.environ.get("STEWARD_CATALOG", "datapack"),
    }
    server = multiprocessing.get_context("spawn").Process(target=_run_streamlit, args=(app_port, env), daemon=True)
    server.start()  # starts while the user types the password, so the loading screen is short

    api = Api(app_port, secret)
    api._window = webview.create_window(
        "BI Steward",
        login_url,
        js_api=api,
        width=LOGIN_SIZE[0],
        height=LOGIN_SIZE[1],
        min_size=(400, 560),
        background_color="#FFFFFF",
    )
    try:
        webview.start()
    finally:
        server.terminate()
        server.join(timeout=5)


if __name__ == "__main__":
    multiprocessing.freeze_support()  # PyInstaller: the spawned server process starts from the frozen app
    main()
