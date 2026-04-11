#!/usr/bin/env python3
"""
energy-usage-graph view updater.

Purpose:
    Fetch today's hourly energy statistics from HA and write data.json for
    the chart view to consume.

Responsibilities:
    - Discover grid, solar, and export entities from HA energy configuration
    - Fetch hourly statistics; fall back to yesterday when today has no data yet
    - Compute net solar consumption (solar generated minus grid export)
    - Write structured JSON to the view's data.json

Key assumptions:
    - HA energy config uses flat stat_energy_from/stat_energy_to on each source
    - Statistics timestamps are Unix milliseconds (13-digit integers)
    - Timezone: Asia/Bangkok (UTC+7), no DST
    - Called by HA shell_command every 5 minutes
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.ha import HaWebSocket, configure_logging, error_output, load_token, write_json

OUTPUT_FILE = "/config/www/views/energy-usage-graph/data.json"
BANGKOK     = timezone(timedelta(hours=7))

log = configure_logging("energy-usage-graph.update")


def fetch_entity_roles(ws: HaWebSocket) -> dict[str, str]:
    """Return {entity_id: role} derived from HA energy configuration."""
    prefs: dict = ws.request({"type": "energy/get_prefs"}) or {}
    roles: dict[str, str] = {}
    for source in prefs.get("energy_sources", []):
        if source["type"] == "grid":
            if source.get("stat_energy_from"):
                roles[source["stat_energy_from"]] = "grid_from"
            if source.get("stat_energy_to"):
                roles[source["stat_energy_to"]] = "grid_to"
        elif source["type"] == "solar":
            if source.get("stat_energy_from"):
                roles[source["stat_energy_from"]] = "solar"
    if not roles:
        raise RuntimeError("No energy entities found in HA energy configuration")
    return roles


def fetch_hourly_stats(ws: HaWebSocket, entity_roles: dict[str, str],
                       start: datetime, end: datetime) -> dict:
    """Return raw HA hourly statistics for the given entities and period."""
    return ws.request({
        "type":          "recorder/statistics_during_period",
        "start_time":    start.isoformat(),
        "end_time":      end.isoformat(),
        "statistic_ids": list(entity_roles),
        "period":        "hour",
        "types":         ["change"],
    }) or {}


def parse_hourly_stats(stats: dict,
                       entity_roles: dict[str, str]) -> tuple[dict, dict, dict]:
    """Parse raw stats into {hour: kWh} dicts for grid_from, grid_to, and solar."""
    buckets: dict[str, dict[int, float]] = {"grid_from": {}, "grid_to": {}, "solar": {}}
    for entity_id, rows in stats.items():
        role = entity_roles.get(entity_id)
        if role not in buckets:
            continue
        target = buckets[role]
        for row in rows:
            s = row["start"]
            ms = s if isinstance(s, (int, float)) else int(
                datetime.fromisoformat(s).timestamp() * 1000
            )
            hour = (
                datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
                .astimezone(BANGKOK)
                .hour
            )
            value = row.get("change") or 0
            if value > 0:
                target[hour] = target.get(hour, 0.0) + value
    return buckets["grid_from"], buckets["grid_to"], buckets["solar"]


def build_result(day_start: datetime,
                 grid_from: dict, grid_to: dict, solar: dict) -> dict:
    """Assemble the JSON payload consumed by index.html."""
    all_hours = sorted(set(grid_from) | set(grid_to) | set(solar))

    def hour_ts(h: int) -> int:
        return int((day_start + timedelta(hours=h)).timestamp() * 1000)

    return {
        "date":          day_start.strftime("%Y-%m-%d"),
        "start_ms":      int(day_start.timestamp() * 1000),
        "end_ms":        int((day_start + timedelta(hours=23)).timestamp() * 1000),
        "timestamps":    [hour_ts(h) for h in all_hours],
        "grid_consumed": [round(grid_from.get(h, 0.0), 3) for h in all_hours],
        "solar_used":    [round(max(0.0, solar.get(h, 0.0) - grid_to.get(h, 0.0)), 3)
                          for h in all_hours],
        "grid_exported": [round(-grid_to.get(h, 0.0), 3) for h in all_hours],
        "updated":       datetime.now(BANGKOK).isoformat(),
    }


def main() -> None:
    token = load_token()
    now   = datetime.now(BANGKOK)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    with HaWebSocket(token) as ws:
        entity_roles = fetch_entity_roles(ws)
        log.info("Energy entities: %s", list(entity_roles))

        stats = fetch_hourly_stats(ws, entity_roles, today, now)
        grid_from, grid_to, solar = parse_hourly_stats(stats, entity_roles)

        if not (grid_from or grid_to or solar):
            log.info("No data for today; falling back to yesterday")
            yesterday = today - timedelta(days=1)
            stats = fetch_hourly_stats(ws, entity_roles, yesterday, today)
            grid_from, grid_to, solar = parse_hourly_stats(stats, entity_roles)
            today = yesterday

    log.info("Parsed %d hours of data", len(set(grid_from) | set(grid_to) | set(solar)))
    result = build_result(today, grid_from, grid_to, solar)
    write_json(OUTPUT_FILE, result)
    log.info("Wrote %s", OUTPUT_FILE)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        error_output(OUTPUT_FILE, exc, log)
