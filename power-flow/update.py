#!/usr/bin/env python3
"""
power-flow view updater.

Purpose:
    Fetch the current state of power-flow entities from HA and write data.json
    for the card view to consume.

Responsibilities:
    - Fetch configured entity states from the HA REST API
    - Write the state objects as JSON for browser polling

Key assumptions:
    - Entity IDs must match those configured in index.html
    - Called by HA shell_command every 15 seconds
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.ha import configure_logging, error_output, load_token, rest_get, write_json

OUTPUT_FILE = "/config/www/views/power-flow/data.json"

ENTITIES = frozenset({
    "sensor.wit_grid_w",
    "sensor.wit_solar_w",
    "sensor.wit_house_kw",
    "sensor.electricity_maps_grid_fossil_fuel_percentage",
})

log = configure_logging("power-flow.update")


def main() -> None:
    token  = load_token()
    states = rest_get("/api/states", token)
    result = {s["entity_id"]: s for s in states if s["entity_id"] in ENTITIES}

    missing = ENTITIES - result.keys()
    if missing:
        log.warning("Missing entities: %s", sorted(missing))

    write_json(OUTPUT_FILE, result)
    log.info("Wrote %s with %d entities", OUTPUT_FILE, len(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        error_output(OUTPUT_FILE, exc, log)
