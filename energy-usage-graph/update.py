#!/usr/bin/env python3
# energy-usage-graph — fetch today's hourly energy stats from HA and write to
# www/views/energy-usage-graph/data.json
# Uses HA WebSocket API: energy/get_prefs + recorder/statistics_during_period
# Token is read from /config/myapp/secrets.json — never exposed to the browser.
# Called by HA shell_command every 5 minutes.

import json
import websocket
from datetime import datetime, timezone, timedelta

SECRETS_FILE = "/config/myapp/secrets.json"
OUTPUT_FILE  = "/config/www/views/energy-usage-graph/data.json"
HA_WS_URL    = "ws://localhost:8123/api/websocket"
BANGKOK      = timezone(timedelta(hours=7))


def recv_id(ws, msg_id):
    while True:
        data = json.loads(ws.recv())
        if data.get("id") == msg_id:
            if not data.get("success", True):
                raise RuntimeError(f"WS error id={msg_id}: {data.get('error')}")
            return data.get("result")


def run():
    with open(SECRETS_FILE) as f:
        token = json.load(f)["token"]

    ws = websocket.create_connection(HA_WS_URL, timeout=15)

    json.loads(ws.recv())  # auth_required
    ws.send(json.dumps({"type": "auth", "access_token": token}))
    auth = json.loads(ws.recv())
    if auth["type"] != "auth_ok":
        raise RuntimeError(f"Auth failed: {auth}")

    ws.send(json.dumps({"id": 1, "type": "energy/get_prefs"}))
    prefs = recv_id(ws, 1)

    entity_roles = {}  # entity_id -> "grid_from" | "grid_to" | "solar"
    for source in prefs.get("energy_sources", []):
        if source["type"] == "grid":
            if source.get("stat_energy_from"):
                entity_roles[source["stat_energy_from"]] = "grid_from"
            if source.get("stat_energy_to"):
                entity_roles[source["stat_energy_to"]] = "grid_to"
        elif source["type"] == "solar":
            if source.get("stat_energy_from"):
                entity_roles[source["stat_energy_from"]] = "solar"

    if not entity_roles:
        raise RuntimeError("No energy entities in HA energy config")

    now   = datetime.now(BANGKOK)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    ws.send(json.dumps({
        "id": 2,
        "type": "recorder/statistics_during_period",
        "start_time": start.isoformat(),
        "end_time":   now.isoformat(),
        "statistic_ids": list(entity_roles),
        "period": "hour",
        "types": ["change"],
    }))
    stats = recv_id(ws, 2)
    ws.close()

    grid_from = {}
    grid_to   = {}
    solar     = {}

    for eid, rows in (stats or {}).items():
        role = entity_roles.get(eid)
        target = {"grid_from": grid_from, "grid_to": grid_to, "solar": solar}.get(role)
        if target is None:
            continue
        for row in rows:
            s = row["start"]
            ms = s if isinstance(s, (int, float)) else int(datetime.fromisoformat(s).timestamp() * 1000)
            t = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
            h = t.astimezone(BANGKOK).hour
            v = row.get("change") or 0
            if v and v > 0:
                target[h] = target.get(h, 0.0) + v

    all_hours = sorted(set(grid_from) | set(grid_to) | set(solar))

    # Midpoint timestamp for each hour (ms) — centers bars on the hour like HA does
    def hour_ts(h):
        return int((start + timedelta(hours=h, minutes=30)).timestamp() * 1000)

    result = {
        "date":          now.strftime("%Y-%m-%d"),
        "start_ms":      int(start.timestamp() * 1000),
        "end_ms":        int(now.replace(minute=0, second=0, microsecond=0).timestamp() * 1000),
        "timestamps":    [hour_ts(h) for h in all_hours],
        "grid_consumed": [round(grid_from.get(h, 0.0), 3) for h in all_hours],
        "solar_used":    [round(max(0.0, solar.get(h, 0.0) - grid_to.get(h, 0.0)), 3) for h in all_hours],
        "grid_exported": [round(-grid_to.get(h, 0.0), 3) for h in all_hours],
        "updated":       now.isoformat(),
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(result, f)


try:
    run()
except Exception as e:
    try:
        with open(OUTPUT_FILE, "w") as f:
            json.dump({"_error": str(e)}, f)
    except Exception:
        pass
