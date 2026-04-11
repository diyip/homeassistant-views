# energy-usage-graph

Standalone hourly energy usage bar chart that visually matches HA's built-in
`hui-energy-usage-graph-card`. Entities are derived automatically from HA's
Energy configuration — no hardcoded sensor IDs.

Served at: `/local/views/energy-usage-graph/index.html`

---

## How it works

```
HA WebSocket API
  └─ energy/get_prefs              discovers grid/solar/export entities
  └─ statistics_during_period      fetches today's hourly kWh changes
        │
        ▼
  update.py  ──writes──  data.json  ──fetch──  index.html (ECharts)
```

`update.py` runs inside the HA container every 5 minutes via shell_command.
`index.html` polls `data.json` every 5 minutes and re-renders the chart.

---

## Data flow detail

### 1. Entity discovery (`energy/get_prefs`)

HA energy config uses a flat structure per source:

```
grid source  →  stat_energy_from  →  role: grid_from  (consumption, kWh)
             →  stat_energy_to    →  role: grid_to    (export, kWh)
solar source →  stat_energy_from  →  role: solar      (generation, kWh)
```

`flow_from[]` / `flow_to[]` nested arrays are **not** used.

### 2. Statistics fetch (`recorder/statistics_during_period`)

- Period: `hour`, type: `change` (delta per hour, not cumulative)
- Range: today midnight → now (Bangkok time)
- Timestamps returned as Unix **milliseconds** (13-digit integers)

### 3. Derived values

```
solar_used    = max(0, solar_generated − grid_exported)
grid_consumed = grid_from  (raw from HA)
grid_exported = −grid_to   (negated for below-axis rendering)
```

### 4. Yesterday fallback

If today has no data yet (e.g. at midnight), `update.py` automatically
re-fetches yesterday's full day and labels the chart with yesterday's date.
Once today's first hourly stat arrives, the chart switches back automatically.

---

## data.json schema

Written to `/config/www/views/energy-usage-graph/data.json`:

```json
{
  "date":          "2026-04-11",
  "start_ms":      1775840400000,
  "end_ms":        1775922000000,
  "timestamps":    [1775840400000, 1775844000000, ...],
  "grid_consumed": [1.234, 0.987, ...],
  "solar_used":    [0.0,   1.456, ...],
  "grid_exported": [-0.0,  -0.321, ...],
  "updated":       "2026-04-11T09:05:00.123456+07:00"
}
```

| Field | Type | Description |
|---|---|---|
| `date` | string | Date label shown on chart (`YYYY-MM-DD`) |
| `start_ms` | int | Midnight of the displayed day (Unix ms) |
| `end_ms` | int | `start_ms + 23 h` — matches HA's `getSuggestedMax` |
| `timestamps` | int[] | Hour-start timestamps (Unix ms) for hours with any data |
| `grid_consumed` | float[] | Grid consumption per hour (kWh, ≥ 0) |
| `solar_used` | float[] | Net solar used locally per hour (kWh, ≥ 0) |
| `grid_exported` | float[] | Grid export per hour (kWh, ≤ 0, negative for chart) |
| `updated` | string | ISO 8601 timestamp of last successful update |

On error: `{"_error": "message"}` — chart displays the error string.

---

## Chart implementation (index.html)

Rendered with **ECharts** (`/local/echarts.min.js`), matching HA's visual style.

### Colors

| Series | CSS variable | Default |
|---|---|---|
| Solar used | `--energy-solar-color` | `#ff9800` |
| Grid consumed | `--energy-grid-consumption-color` | `#488fc2` |
| Grid exported | `--energy-grid-return-color` | `#8353d1` |

Bar fill uses 50% alpha (`color + "7F"`) with full-opacity border — matching
HA's `getEnergyColor(color, true)` behaviour.

### Axis behaviour

- `xAxis.type: "time"`, `min: start_ms`, `max: end_ms` (23:00 today)
- `end_ms = start + 23 h` mirrors HA's `getSuggestedMax` which rounds
  `endOfToday()` (23:59:59) down to the hour for the hourly period
- `barCategoryGap: "15%"` tuned to match HA's bar density
- Rounded caps: top-left/top-right on the topmost positive bar per column;
  bottom-left/bottom-right on the bottommost negative bar per column

### Tooltip

Shows `HH:00 – HH+1:00` header, each non-zero series value in kWh
(3 decimal places below 0.1 kWh), and a bold **Total consumed** line
when more than one positive series is visible.

### Theme

Follows `prefers-color-scheme`. Reloads the page on system theme change
to re-initialise ECharts with the correct dark/light palette.

---

## URL parameters

| Parameter | Default | Description |
|---|---|---|
| `name` | _(none)_ | Page title shown above chart; also sets `document.title` |

---

## Refresh schedule

| Component | Interval | Mechanism |
|---|---|---|
| `update.py` | 5 minutes | HA `time_pattern` automation (`minutes: "/5"`) |
| `index.html` | 5 minutes | `setInterval(refresh, 300000)` |

---

## Local files required

| Path | Purpose |
|---|---|
| `/local/echarts.min.js` | ECharts v5 charting library |

---

## Visual comparison

```bash
cd /config/myapp/views/energy-usage-graph

python3 compare.py --save-session   # once per HA instance — saves shared session
python3 compare.py                  # → ~/tmp/views-compare/energy-usage-graph/compare_light.png
                                    #   ~/tmp/views-compare/energy-usage-graph/compare_dark.png
```

Instance config (`ha_url`, `ha_views_compare_path`) is read from `myapp/settings.json`.
The shared session lives at `~/.config/ha-views/session.json` — one session for all views.
The reference `hui-energy-usage-graph-card` must be present on the dashboard at
`ha_views_compare_path` (currently `lovelace-test/ha-views`).
