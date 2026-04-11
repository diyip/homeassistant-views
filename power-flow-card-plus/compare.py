#!/usr/bin/env python3
"""
Visual comparison for power-flow-card-plus: standalone page vs HA Lovelace card.

Usage:
    python3 compare.py --save-session   # once per HA instance — saves shared session
    python3 compare.py                  # → ~/tmp/views-compare/power-flow-card-plus/
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.compare import run

if __name__ == "__main__":
    run(
        standalone_path="/local/views/power-flow-card-plus/index.html",
        ha_selector="power-flow-card-plus",
        ha_label="HA Lovelace",
        standalone_selector="power-flow-card-plus",
    )
