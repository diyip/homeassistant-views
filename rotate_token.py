#!/usr/bin/env python3
"""
HA Long-Lived Access Token rotation script.

Run daily via cron. Handles scheduling, retry, and failure notification.

Rotation schedule : every 180 days
New token lifespan: 365 days
Notify after      : 3 consecutive daily failures
Re-notify every   : 7 days while still failing
"""

import base64
import json
import logging
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lib.ha import (
    HaWebSocket, HA_REST_URL, SECRETS_FILE,
    _SSL_CONTEXT, configure_logging, write_json,
)

ROTATION_INTERVAL_DAYS = 180
TOKEN_LIFESPAN_DAYS    = 365
NOTIFY_AFTER_FAILURES  = 3
RENOTIFY_INTERVAL_DAYS = 7

STATE_FILE = str(Path(__file__).parent / "token_rotation_state.json")
LOG_FILE   = str(Path(__file__).parent / "rotate_token.log")

NOTIFY_SERVICES = [
    "persistent_notification/create",
    "notify/mobile_app_t_chutiwat",
]

log = configure_logging("rotate_token")


# ── Helpers ──────────────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _trim_log(max_bytes: int = 512 * 1024) -> None:
    """Keep the log under max_bytes by discarding the oldest half when exceeded."""
    try:
        p = Path(LOG_FILE)
        if not p.exists() or p.stat().st_size <= max_bytes:
            return
        data = p.read_bytes()
        p.write_bytes(data[-(max_bytes // 2):])
    except OSError:
        pass


def days_since(iso: str | None) -> float:
    if not iso:
        return float("inf")
    return (utcnow() - datetime.fromisoformat(iso)).total_seconds() / 86400


def token_iss(token: str) -> str:
    """Extract the refresh_token_id (iss claim) from a HA JWT."""
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.b64decode(payload))["iss"]


def load_token() -> str:
    with open(SECRETS_FILE) as f:
        return json.load(f)["ha_token"]


def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"last_rotation": None, "first_failure": None,
                "failure_count": 0, "last_notified": None}


def save_state(state: dict) -> None:
    write_json(STATE_FILE, state)


# ── Core operations ───────────────────────────────────────────────────────────

def verify_token(token: str) -> bool:
    try:
        req = urllib.request.Request(
            f"{HA_REST_URL}/api/",
            headers={"Authorization": f"Bearer {token}"},
        )
        urllib.request.urlopen(req, timeout=5, context=_SSL_CONTEXT)
        return True
    except Exception:
        return False


def delete_token(auth_token: str, refresh_token_id: str) -> None:
    with HaWebSocket(auth_token) as ws:
        ws.request({"type": "auth/delete_refresh_token",
                    "refresh_token_id": refresh_token_id})


def notify(token: str, title: str, message: str) -> None:
    for svc in NOTIFY_SERVICES:
        try:
            payload = json.dumps({"title": title, "message": message}).encode()
            req = urllib.request.Request(
                f"{HA_REST_URL}/api/services/{svc}",
                data=payload,
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5, context=_SSL_CONTEXT)
            log.info("Notification sent via %s", svc)
        except Exception as e:
            log.warning("Notification via %s failed: %s", svc, e)


def _cleanup_orphan(auth_token: str) -> None:
    """Delete any update_py_* token that is not the currently active token.
    Catches orphans from failed attempts AND superseded tokens after rotation."""
    current_iss = token_iss(auth_token)
    try:
        with HaWebSocket(auth_token) as ws:
            tokens = ws.request({"type": "auth/refresh_tokens"})
        for t in (tokens or []):
            if ((t.get("client_name") or "").startswith("ha_views_")
                    and t["id"] != current_iss):
                delete_token(auth_token, t["id"])
                log.info("Stale token cleaned up (client_name=%s)", t["client_name"])
    except Exception as e:
        log.warning("Orphan cleanup failed (non-fatal): %s", e)


def rotate(current_token: str) -> None:
    """Full rotation: create → verify → update secrets.json → delete old."""
    old_iss = token_iss(current_token)
    client_name = f"ha_views_{utcnow().strftime('%Y%m%d')}"

    # Clean up any orphan from a previous failed attempt with the same name
    _cleanup_orphan(current_token)

    # Create
    log.info("Creating new token (client_name=%s, lifespan=%dd)",
             client_name, TOKEN_LIFESPAN_DAYS)
    with HaWebSocket(current_token) as ws:
        new_token = ws.request({
            "type": "auth/long_lived_access_token",
            "client_name": client_name,
            "lifespan": TOKEN_LIFESPAN_DAYS,
        })
    if not isinstance(new_token, str):
        raise RuntimeError(f"Unexpected create response: {new_token!r}")
    new_iss = token_iss(new_token)

    # Verify — clean up orphan on failure
    if not verify_token(new_token):
        try:
            delete_token(current_token, new_iss)
        except Exception:
            pass
        raise RuntimeError("New token failed verification")

    # Persist — clean up orphan if write fails
    try:
        write_json(SECRETS_FILE, {"ha_token": new_token})
        log.info("secrets.json updated")
    except Exception as write_err:
        try:
            delete_token(current_token, new_iss)
            log.info("Orphaned new token cleaned up after write failure")
        except Exception:
            pass
        raise RuntimeError(f"Failed to write secrets.json: {write_err}") from write_err

    # Delete old (non-fatal if it fails)
    try:
        delete_token(new_token, old_iss)
        log.info("Old token deleted")
    except Exception as e:
        log.warning("Old token deletion failed (non-fatal): %s", e)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    _trim_log()
    state     = load_state()
    cur_token = load_token()

    rotation_due  = days_since(state["last_rotation"]) >= ROTATION_INTERVAL_DAYS
    retry_pending = state["failure_count"] > 0

    if not rotation_due and not retry_pending:
        log.info("No rotation needed (last: %s, next in ~%.0f days)",
                 state["last_rotation"],
                 ROTATION_INTERVAL_DAYS - days_since(state["last_rotation"]))
        return

    reason = "scheduled" if rotation_due else f"retry #{state['failure_count']}"
    log.info("Starting rotation (%s)", reason)

    try:
        rotate(cur_token)

        state.update({"last_rotation": utcnow().isoformat(),
                      "first_failure": None,
                      "failure_count": 0,
                      "last_notified": None})
        save_state(state)
        log.info("Rotation complete")

    except Exception as e:
        log.error("Rotation failed: %s", e)

        state["failure_count"] = state.get("failure_count", 0) + 1
        if not state["first_failure"]:
            state["first_failure"] = utcnow().isoformat()

        if (state["failure_count"] >= NOTIFY_AFTER_FAILURES
                and days_since(state["last_notified"]) >= RENOTIFY_INTERVAL_DAYS):
            msg = (
                f"Token rotation has failed {state['failure_count']} consecutive times.\n"
                f"First failure: {state['first_failure']}\n"
                f"Latest error: {e}\n\n"
                f"Please rotate manually:\n"
                f"HA UI → Profile → Long-Lived Access Tokens"
            )
            notify(cur_token, "Token Rotation Failed", msg)
            state["last_notified"] = utcnow().isoformat()

        save_state(state)
        sys.exit(1)


if __name__ == "__main__":
    main()
