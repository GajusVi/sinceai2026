"""Desktop app login handover (DECISION T2.6): the native login window checks the password, then opens the
workspace with a short-lived signed token, so the user signs in once.

The launcher (app/main.py) makes a random secret per run and passes it to the Streamlit server in
STEWARD_APP_SECRET; only that process can verify the token. A mock login stays a mock: this keeps the two windows of
one run honest, it is not company authentication.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time

ENV_SECRET = "STEWARD_APP_SECRET"
ENV_LOGIN_URL = "STEWARD_APP_LOGIN_URL"  # where "Log out" returns the window
MAX_AGE_S = 120


def sign(username: str, secret: str, now: float | None = None) -> str:
    ts = str(int(now if now is not None else time.time()))
    mac = hmac.new(secret.encode(), f"{username}|{ts}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{ts}.{mac}"


def verify(username: str, token: str, secret: str | None = None, now: float | None = None) -> bool:
    secret = secret if secret is not None else os.environ.get(ENV_SECRET, "")
    if not secret or not username or "." not in (token or ""):
        return False
    ts, _ = token.split(".", 1)
    if not ts.isdigit() or abs((now if now is not None else time.time()) - int(ts)) > MAX_AGE_S:
        return False
    return hmac.compare_digest(sign(username, secret, int(ts)), token)


def app_mode() -> bool:
    """True when the desktop launcher started this server."""
    return bool(os.environ.get(ENV_SECRET))
