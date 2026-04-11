#!/usr/bin/env python3
"""
Visual comparison for energy-usage-graph: standalone page vs HA energy card.

Usage:
    python3 compare.py --save-session   # once per HA instance — saves shared session
    python3 compare.py                  # → ~/tmp/views-compare/energy-usage-graph/
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.compare import run

if __name__ == "__main__":
    run(
        standalone_path="/local/views/energy-usage-graph/index.html",
        ha_selector="hui-energy-usage-graph-card",
        ha_label="HA Energy",
    )
