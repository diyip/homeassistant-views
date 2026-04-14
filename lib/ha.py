#!/usr/bin/env python3
"""
Shared HA client utilities for view update scripts.

Purpose:
    Centralise everything needed to authenticate with HA, call its APIs, write
    output files safely, and report errors consistently.

Responsibilities:
    - Load the long-lived access token from secrets.json
    - Perform authenticated HTTP GET requests via the HA REST API
    - Manage an authenticated WebSocket connection to the HA API
    - Write JSON output atomically to prevent partial browser reads
    - Configure consistent structured logging across all scripts
    - Write {"_error": ...} output on failure so the browser stays informed

Key assumptions:
    - Scripts run inside the HA Docker container (/config = HA config directory)
    - Secrets are stored at SECRETS_FILE as {"token": "..."}
    - websocket-client and urllib are available in the container environment
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

import websocket

# Inside the HA container /config is the config dir; on the host it lives under
# the hassio homeassistant directory.  Resolve whichever exists.
def _config_root() -> str:
    import os
    if os.path.isdir("/config"):
        return "/config"
    # Walk up from this file: lib/ → views/ → myapp/ → homeassistant/
    return str(Path(__file__).resolve().parents[3])

_CONFIG_ROOT  = _config_root()
SECRETS_FILE  = f"{_CONFIG_ROOT}/myapp/views/secrets.json"
SETTINGS_FILE = f"{_CONFIG_ROOT}/myapp/views/settings.json"


def _internal_base_url() -> str:
    """Derive the best reachable HA base URL from settings.json.

    Tries localhost first (works when running inside the HA Docker container),
    then falls back to the external URL from settings.json (works on the host).
    """
    with open(SETTINGS_FILE) as f:
        ha_url = json.load(f)["ha_url"].rstrip("/")
    parsed = urllib.parse.urlparse(ha_url)
    port   = parsed.port or (443 if parsed.scheme == "https" else 80)
    local  = f"{parsed.scheme}://localhost:{port}"
    try:
        req = urllib.request.Request(f"{local}/api/", headers={"Authorization": "Bearer test"})
        urllib.request.urlopen(req, timeout=2, context=ssl._create_unverified_context())
    except urllib.error.HTTPError:
        return local   # got a real HTTP response (e.g. 401) — localhost works
    except OSError:
        return ha_url  # connection refused or network error — use external URL
    return local


_BASE_URL    = _internal_base_url()
_WS_SCHEME   = "wss" if _BASE_URL.startswith("https") else "ws"
_WS_BASE_URL = _WS_SCHEME + _BASE_URL[_BASE_URL.index("://"):]

HA_REST_URL  = _BASE_URL
HA_WS_URL    = f"{_WS_BASE_URL}/api/websocket"

_SSL_CONTEXT = ssl._create_unverified_context()


def configure_logging(name: str) -> logging.Logger:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        level=logging.INFO,
    )
    return logging.getLogger(name)


def load_token(path: str = SECRETS_FILE) -> str:
    with open(path) as f:
        return json.load(f)["ha_token"]


def rest_get(path: str, token: str, timeout: int = 5):
    req = urllib.request.Request(
        f"{HA_REST_URL}{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT).read())


def write_json(path: str, data: dict) -> None:
    """Write data as JSON, ensuring the file is world-readable after write."""
    with open(path, "w") as f:
        json.dump(data, f)
    os.chmod(path, 0o644)


def error_output(output_file: str, exc: Exception,
                 logger: logging.Logger | None = None) -> None:
    """Log exc and write {"_error": ...} to output_file."""
    if logger:
        logger.error("Update failed: %s", exc, exc_info=True)
    try:
        write_json(output_file, {"_error": str(exc)})
    except Exception:
        pass


class HaWebSocket:
    """Authenticated HA WebSocket connection usable as a context manager.

    Handles the auth handshake automatically and tracks message IDs.
    Raises RuntimeError if authentication fails or a request returns an error.
    """

    def __init__(self, token: str, url: str = HA_WS_URL, timeout: int = 15):
        self._token   = token
        self._url     = url
        self._timeout = timeout
        self._conn    = None
        self._next_id = 1

    def __enter__(self) -> HaWebSocket:
        self._conn = websocket.create_connection(
            self._url, timeout=self._timeout, sslopt={"cert_reqs": ssl.CERT_NONE}
        )
        self._conn.recv()  # auth_required frame
        self._conn.send(json.dumps({"type": "auth", "access_token": self._token}))
        auth = json.loads(self._conn.recv())
        if auth["type"] != "auth_ok":
            raise RuntimeError(f"WebSocket authentication failed: {auth}")
        return self

    def __exit__(self, *_) -> None:
        if self._conn:
            self._conn.close()

    def request(self, payload: dict) -> dict | None:
        """Send a request and block until the matching response arrives."""
        msg_id = self._next_id
        self._next_id += 1
        self._conn.send(json.dumps({"id": msg_id, **payload}))
        while True:
            msg = json.loads(self._conn.recv())
            if msg.get("id") == msg_id:
                if not msg.get("success", True):
                    raise RuntimeError(f"HA error (id={msg_id}): {msg.get('error')}")
                return msg.get("result")
