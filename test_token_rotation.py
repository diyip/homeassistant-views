#!/usr/bin/env python3
"""
Test script for HA LLAT rotation via WebSocket API.

Safe to run anytime — it only creates a temporary 1-day test token,
verifies it works, then deletes it. The production token in secrets.json
is never modified.

Usage:
    python3 test_token_rotation.py
"""

import json
import sys
import urllib.request
import ssl

sys.path.insert(0, str(__import__('pathlib').Path(__file__).parent))
from lib.ha import load_token, HaWebSocket, HA_REST_URL, _SSL_CONTEXT

import time as _time
TEST_CLIENT_NAME = f"rotate_test_{int(_time.time())}"
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = PASS if ok else FAIL
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    return ok


def verify_token(token: str) -> bool:
    """Call GET /api/ with the given token; return True if HTTP 200."""
    try:
        req = urllib.request.Request(
            f"{HA_REST_URL}/api/",
            headers={"Authorization": f"Bearer {token}"},
        )
        urllib.request.urlopen(req, timeout=5, context=_SSL_CONTEXT)
        return True
    except Exception as e:
        print(f"         verify error: {e}")
        return False


def main():
    print("\n=== HA Token Rotation — Test Run ===\n")
    all_ok = True

    token = load_token()
    print(f"  Production token loaded (last 8 chars: ...{token[-8:]})\n")

    # Step 1: Create a temporary test token
    print("Step 1: Create temporary test token (lifespan=1 day)")
    new_token = None
    refresh_token_id = None
    try:
        with HaWebSocket(token) as ws:
            result = ws.request({
                "type": "auth/long_lived_access_token",
                "client_name": TEST_CLIENT_NAME,
                "lifespan": 1,
            })
        print(f"         Raw result: {json.dumps(result, indent=2)}")
        if isinstance(result, str):
            new_token = result
        elif isinstance(result, dict):
            new_token = result.get("token") or result.get("access_token")
            refresh_token_id = result.get("refresh_token_id") or result.get("id")
        ok = new_token is not None
        all_ok &= check("Token created", ok, f"...{new_token[-8:]}" if ok else "no token in result")
    except Exception as e:
        all_ok &= check("Token created", False, str(e))

    # Step 2: Verify the new token works
    print("\nStep 2: Verify new token authenticates with HA")
    if new_token:
        ok = verify_token(new_token)
        all_ok &= check("New token is valid", ok)
    else:
        all_ok &= check("New token is valid", False, "skipped — no token from step 1")

    # Step 3: Extract refresh_token_id from JWT iss claim
    print("\nStep 3: Extract refresh_token_id from JWT iss claim")
    if new_token and not refresh_token_id:
        try:
            import base64
            payload = new_token.split('.')[1]
            payload += '=' * (-len(payload) % 4)
            claims = json.loads(base64.b64decode(payload))
            refresh_token_id = claims.get('iss')
            all_ok &= check("refresh_token_id found", refresh_token_id is not None,
                            str(refresh_token_id) if refresh_token_id else "no iss in JWT")
        except Exception as e:
            all_ok &= check("refresh_token_id found", False, str(e))
    elif refresh_token_id:
        check("refresh_token_id found", True, f"returned by create: {refresh_token_id}")
    else:
        check("refresh_token_id found", False, "skipped — no token from step 1")

    # Step 4: Delete the test token
    print("\nStep 4: Delete the test token")
    if refresh_token_id:
        try:
            with HaWebSocket(token) as ws:
                ws.request({
                    "type": "auth/delete_refresh_token",
                    "refresh_token_id": refresh_token_id,
                })
            all_ok &= check("Test token deleted", True)
        except Exception as e:
            all_ok &= check("Test token deleted", False, str(e))
    else:
        all_ok &= check("Test token deleted", False, "skipped — no refresh_token_id")

    # Step 5: Confirm deleted token no longer works
    print("\nStep 5: Confirm deleted token is rejected")
    if new_token and refresh_token_id:
        rejected = not verify_token(new_token)
        all_ok &= check("Deleted token is rejected", rejected)
    else:
        check("Deleted token is rejected", False, "skipped")

    print(f"\n{'='*38}")
    if all_ok:
        print(f"  [{PASS}] All steps passed — rotation mechanism works.")
        print("  Ready to build the production rotation script.")
    else:
        print(f"  [{FAIL}] Some steps failed — review output above before proceeding.")
    print()


if __name__ == "__main__":
    main()
