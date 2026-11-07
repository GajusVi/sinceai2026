"""Live data for exported PBIP files: the report's tables refresh from this app (user chose "option 2").

An export in live mode does not embed the data. Each table loads `http://127.0.0.1:<port>/pbip/<id>/<table>.json?key=<key>`
from this module, so Power BI Desktop's Refresh pulls the governed numbers from the app. The rows come from the same code
as the embedded export (`pbip._prepare` + `semantic.scoped_frames`), so the two cannot differ (tests compare them).

Rules:
- Standard library only (no uvicorn): it must run inside the packaged desktop app.
- Binds to 127.0.0.1 only. Every export has its own key (HMAC of the id with a secret kept in the data dir); a wrong key is 403.
- A revoked decision answers 410, so Refresh fails with a clear message instead of showing numbers nobody stands behind.
- NOT authentication: the app's login is a mock. The key keeps one export from reading another's data, nothing more.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .pbip import _cell, _prepare
from .semantic import load_frames, scoped_frames
from .spec import DashboardSpec

HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("STEWARD_PBIP_PORT", "8765"))
FOLDER = "pbip_live"
REVOKED_FILE = "revoked.json"
_PATH = re.compile(r"^/pbip/([0-9a-f]{16})/([A-Za-z0-9_]{1,64})\.json$")


@dataclass(frozen=True)
class LiveSource:
    """Where an exported report loads its data from."""

    base_url: str
    id: str
    key: str

    def table_url(self, entity: str) -> str:
        return f"{self.base_url}/pbip/{self.id}/{entity}.json"


# -- registry (files in the data dir) ------------------------------------------------------------------------------


def _folder(data_dir: Path) -> Path:
    folder = Path(data_dir) / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _secret(data_dir: Path) -> bytes:
    path = _folder(data_dir) / ".secret"
    if not path.exists():
        path.write_text(secrets.token_hex(16), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip().encode()


def spec_id(spec: DashboardSpec) -> str:
    """16 hex characters: the spec hash when the pipeline set one, else a hash of the spec itself."""
    given = spec.provenance.get("spec_hash", "")
    if re.fullmatch(r"[0-9a-f]{16}", given):
        return given
    body = spec.model_dump_json(exclude={"lint", "provenance"})
    return hashlib.sha256(body.encode()).hexdigest()[:16]


def key_for(data_dir: Path, spec_id_: str) -> str:
    return hmac.new(_secret(data_dir), spec_id_.encode(), hashlib.sha256).hexdigest()[:24]


def register(spec: DashboardSpec, data_dir: Path, base_url: str) -> LiveSource:
    """Stores the spec so the server can rebuild its tables, and returns the source to put in the export."""
    sid = spec_id(spec)
    (_folder(data_dir) / f"{sid}.json").write_text(spec.model_dump_json(indent=2), encoding="utf-8")
    return LiveSource(base_url=base_url.rstrip("/"), id=sid, key=key_for(data_dir, sid))


def revoke(data_dir: Path, spec_id_: str) -> None:
    """After this, Refresh in Desktop fails (410) for that export."""
    path = _folder(data_dir) / REVOKED_FILE
    ids = set(json.loads(path.read_text("utf-8"))) if path.exists() else set()
    path.write_text(json.dumps(sorted(ids | {spec_id_})), encoding="utf-8")


def _revoked(data_dir: Path, spec_id_: str) -> bool:
    path = _folder(data_dir) / REVOKED_FILE
    return path.exists() and spec_id_ in json.loads(path.read_text("utf-8"))


# -- the rows ------------------------------------------------------------------------------------------------------


def table_payload(spec: DashboardSpec, frames: dict, entity: str) -> dict:
    """{"columns": [...], "rows": [[...]]} for one table: exactly what the embedded export would carry."""
    scoped = _prepare(scoped_frames(frames, spec.filters))
    if entity not in spec.entities or entity not in scoped:
        raise KeyError(entity)
    frame = scoped[entity]
    wanted = spec.columns.get(entity) or list(frame.columns)
    columns = [c for c in wanted if c in frame.columns]
    rows = [[_cell(v) for v in row] for row in frame[columns].itertuples(index=False, name=None)]
    return {"columns": columns, "rows": rows}


# -- the server ----------------------------------------------------------------------------------------------------


def _handler(data_dir: Path, frames_loader):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # quiet: the app's log is not the place for every refresh
            pass

        def _send(self, code: int, body: dict) -> None:
            data = json.dumps(body, separators=(",", ":"), allow_nan=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802 (http.server API)
            url = urlparse(self.path)
            match = _PATH.match(url.path)
            if not match:
                return self._send(404, {"error": "not found"})
            sid, entity = match.groups()
            given = (parse_qs(url.query).get("key") or [""])[0]
            if not hmac.compare_digest(given, key_for(data_dir, sid)):
                return self._send(403, {"error": "bad key"})
            path = _folder(data_dir) / f"{sid}.json"
            if not path.exists():
                return self._send(404, {"error": "unknown decision"})
            if _revoked(data_dir, sid):
                return self._send(410, {"error": "this decision was revoked; ask the BI team for a new export"})
            spec = DashboardSpec.model_validate_json(path.read_text(encoding="utf-8"))
            try:
                self._send(200, table_payload(spec, frames_loader(), entity))
            except KeyError:
                self._send(404, {"error": "unknown table"})

    return Handler


_RUNNING: dict[str, tuple[ThreadingHTTPServer, str]] = {}
_LOCK = threading.Lock()


def start(data_dir: Path, port: int | None = None, frames_loader=load_frames) -> tuple[ThreadingHTTPServer, str]:
    """Starts a server in a daemon thread. `port=0` picks a free port (tests). Returns (server, base_url)."""
    server = ThreadingHTTPServer((HOST, DEFAULT_PORT if port is None else port), _handler(Path(data_dir), frames_loader))
    threading.Thread(target=server.serve_forever, name="pbip-live", daemon=True).start()
    return server, f"http://{HOST}:{server.server_address[1]}"


def ensure_running(data_dir: Path) -> str:
    """The app calls this when it exports a live report. One server per process, started on first use."""
    key = str(Path(data_dir).resolve())
    with _LOCK:
        if key not in _RUNNING:
            try:
                _RUNNING[key] = start(Path(data_dir))
            except OSError as exc:
                raise RuntimeError(
                    f"The live-refresh service could not start on {HOST}:{DEFAULT_PORT} ({exc}). Another copy of the app "
                    "may be running; close it, or set STEWARD_PBIP_PORT."
                ) from exc
        return _RUNNING[key][1]
