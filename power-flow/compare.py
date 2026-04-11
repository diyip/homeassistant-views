#!/usr/bin/env python3
"""
Visual comparison for power-flow: standalone page vs HA Lovelace card.

Usage:
    python3 compare.py --save-session   # first time: save HA browser session
    python3 compare.py                  # headless → standalone.png, ha.png, compare.png
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.compare import run

STANDALONE_URL = "http://witw31.myqnapcloud.com:52581/local/views/power-flow/index.html"
HA_URL         = "http://witw31.myqnapcloud.com:52581/lovelace-test/12"
HA_SELECTOR    = "power-flow-card-plus"
SESSION_FILE   = Path(__file__).parent / "ha_session.json"

if __name__ == "__main__":
    run(
        standalone_url=STANDALONE_URL,
        ha_url=HA_URL,
        session_file=SESSION_FILE,
        ha_selector=HA_SELECTOR,
        ha_label="HA Lovelace",
        standalone_selector=HA_SELECTOR,
    )
