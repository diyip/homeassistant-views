#!/usr/bin/env python3
# power-flow — fetch entity states from HA and write to www/views/power-flow/data.json
# Token is read from /config/myapp/secrets.json — never exposed to the browser.
# Called by HA shell_command every 15 seconds.

import json
import urllib.request

SECRETS_FILE = "/config/myapp/secrets.json"
OUTPUT_FILE  = "/config/www/views/power-flow/data.json"
HA_URL       = "http://localhost:8123"

ENTITIES = [
    "sensor.wit_grid_w",
    "sensor.wit_solar_w",
    "sensor.wit_house_kw",
    "sensor.electricity_maps_grid_fossil_fuel_percentage",
]

try:
    with open(SECRETS_FILE) as f:
        token = json.load(f)["token"]

    req = urllib.request.Request(
        f"{HA_URL}/api/states",
        headers={"Authorization": f"Bearer {token}"},
    )
    states = json.loads(urllib.request.urlopen(req, timeout=5).read())
    result = {s["entity_id"]: s for s in states if s["entity_id"] in ENTITIES}

    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f)

except Exception as e:
    try:
        with open(OUTPUT_FILE, "w") as f:
            json.dump({"_error": str(e)}, f)
    except Exception:
        pass
