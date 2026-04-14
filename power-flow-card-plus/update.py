#!/usr/bin/env python3
"""
power-flow-card-plus view updater.

Purpose:
    Fetch the current state of power-flow-card-plus entities from HA and write
    data.json for the card view to consume.

Responsibilities:
    - Read card config and entity IDs from settings.json
    - Fetch configured entity states from the HA REST API
    - Write entity states and card config as JSON for browser polling

Key assumptions:
    - Entity IDs and card parameters are configured in settings.json
    - Called by HA shell_command every 15 seconds
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.ha import configure_logging, error_output, load_token, rest_get, write_json

from lib.ha import SETTINGS_FILE

_HA_ROOT    = Path(SETTINGS_FILE).parents[2]
OUTPUT_FILE = str(_HA_ROOT / "www/views/power-flow-card-plus/data.json")

log = configure_logging("power-flow-card-plus.update")


def load_card_config() -> dict:
    with open(SETTINGS_FILE) as f:
        return json.load(f)["power_flow_card_plus"]


def extract_entity_ids(cfg: dict) -> frozenset[str]:
    """Collect all entity IDs referenced in the card config entities block."""
    ids: set[str] = set()
    for key, val in cfg.get("entities", {}).items():
        if key == "individual":
            for item in (val if isinstance(val, list) else [val]):
                if isinstance(item, dict) and item.get("entity"):
                    ids.add(item["entity"])
        elif isinstance(val, dict) and val.get("entity"):
            ids.add(val["entity"])
    return frozenset(ids)


def main() -> None:
    cfg        = load_card_config()
    entity_ids = extract_entity_ids(cfg)

    token  = load_token()
    states = rest_get("/api/states", token)
    result = {s["entity_id"]: s for s in states if s["entity_id"] in entity_ids}

    missing = entity_ids - result.keys()
    if missing:
        log.warning("Missing entities: %s", sorted(missing))

    result["_config"] = cfg
    write_json(OUTPUT_FILE, result)
    log.info("Wrote %s with %d entities", OUTPUT_FILE, len(result) - 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        error_output(OUTPUT_FILE, exc, log)
