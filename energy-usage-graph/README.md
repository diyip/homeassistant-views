# energy-usage-graph

Standalone hourly energy usage bar chart that visually matches HA's built-in
`hui-energy-usage-graph-card`. Entities are derived automatically from HA's
Energy configuration — no hardcoded sensor IDs.

Served at: `/local/views/energy-usage-graph/index.html`

---

## Common use cases

All parameters are optional and can be combined freely.

### 1. Default — today

```
https://yit.yipintsoi.net:48131/local/views/energy-usage-graph/index.html
```

Shows today 00:00 – 23:00 Bangkok time.

---

### 2. Add a page title

```
https://yit.yipintsoi.net:48131/local/views/energy-usage-graph/index.html?name=Car+Park+Energy
```

Shows "CAR PARK ENERGY" above the chart and sets the browser tab title.

---

### 3. Show yesterday + today

```
https://yit.yipintsoi.net:48131/local/views/energy-usage-graph/index.html?days=2
```

Shows yesterday 00:00 through today 23:00 — 2 days total. End is always today 23:00.

---

### 4. Show the past week

```
https://yit.yipintsoi.net:48131/local/views/energy-usage-graph/index.html?days=7
```

Shows the past 7 days. Maximum is `days=7`.

---

### 5. Rolling window

```
https://yit.yipintsoi.net:48131/local/views/energy-usage-graph/index.html?hours=36
```

Last 36 hours from now, rolling — useful for overnight views that span two days.
Maximum is `hours=168` (7 days).

---

### 6. Show date label

```
https://yit.yipintsoi.net:48131/local/views/energy-usage-graph/index.html?show_date=true
```

Shows the date above the chart (hidden by default). Most useful with `days=2` or
more, where the chart spans multiple days.

---

### 7. Full combination

```
https://yit.yipintsoi.net:48131/local/views/energy-usage-graph/index.html?name=Car+Park+Energy&days=7&show_date=true
```

Page title, past week view, and date label — all combined.

---

## URL parameters

| Parameter | Default | Description |
|---|---|---|
| `name` | _(none)_ | Page title shown above chart; also sets `document.title` |
| `days` | _(none)_ | Number of days to show: `1`=today only, `2`=yesterday+today, `7`=past week. End is always today 23:00. Max `7`. |
| `hours` | _(none)_ | Rolling window: last N hours from now. Max `168`. Takes effect only when `days` is not set. |
| `show_date` | `false` | Show the date label above the chart |

---

## How it works

```
HA WebSocket API
  └─ energy/get_prefs              discovers grid/solar/export entities
  └─ statistics_during_period      fetches last 7 days of hourly kWh changes
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

### 2. Statistics fetch (`recorder/statistics_during_period`)

- Period: `hour`, type: `change` (delta per hour, not cumulative)
- Range: last 7 days from now (Bangkok time)
- Timestamps stored as absolute UTC milliseconds floored to the hour boundary
  — unique across days, used directly as ECharts x-values

### 3. Derived values

```
solar_used    = max(0, solar_generated − grid_exported)
grid_consumed = grid_from  (raw from HA)
grid_exported = −grid_to   (negated for below-axis rendering)
```

### 4. Display window (index.html)

`index.html` slices `data.json` to the requested window at render time:

- **Default / `?days=1`** — today midnight to 23:00 Bangkok
- **`?days=N`** — (N-1) days ago midnight to today 23:00 Bangkok
- **`?hours=N`** — rolling `Date.now() − N hours` to now

---

## data.json schema

Written to `<ha-root>/www/views/energy-usage-graph/data.json`
(inside container: `/config/www/views/energy-usage-graph/data.json`).

```json
{
  "date":            "2026-04-14",
  "start_ms":        1775235600000,
  "end_ms":          1775840400000,
  "hours_available": 167,
  "timestamps":      [1775235600000, 1775239200000, ...],
  "grid_consumed":   [1.234, 0.987, ...],
  "solar_used":      [0.0,   1.456, ...],
  "grid_exported":   [-0.0,  -0.321, ...],
  "updated":         "2026-04-14T14:05:00+07:00"
}
```

| Field | Type | Description |
|---|---|---|
| `date` | string | Today's date (`YYYY-MM-DD`) |
| `start_ms` | int | Oldest available data point (Unix ms) |
| `end_ms` | int | Time of last update (Unix ms) |
| `hours_available` | int | Number of hourly buckets in this file |
| `timestamps` | int[] | UTC ms timestamps floored to hour boundary |
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

Bar fill uses 50% alpha (`color + "7F"`), matching HA's `getEnergyColor(color, true)`.

### Axis behaviour

- `xAxis.type: "time"`, `min/max` computed from the requested window
- Date labels appear at midnight boundaries when the chart spans multiple days
- `barCategoryGap: "15%"` tuned to match HA's bar density
- Rounded caps: top corners on positive bars, bottom corners on export bars

### Tooltip

Shows `HH:00 – HH+1:00` header, each non-zero series value in kWh
(3 decimal places below 0.1 kWh), and a bold **Total consumed** line
when more than one positive series is visible.

### Theme

Follows `prefers-color-scheme`. Reloads on system theme change to
re-initialise ECharts with the correct dark/light palette.

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
cd <ha-root>/myapp/views/energy-usage-graph   # host path
# or inside the container: cd /config/myapp/views/energy-usage-graph

python3 compare.py --save-session   # once per HA instance — saves shared session
python3 compare.py                  # → ~/tmp/views-compare/energy-usage-graph/compare_light.png
                                    #   ~/tmp/views-compare/energy-usage-graph/compare_dark.png
```

Instance config (`ha_url`, `ha_views_compare_path`) is read from `settings.json`.
The shared session lives at `~/.config/ha-views/session.json` — one session for all views.
The reference `hui-energy-usage-graph-card` must be present on the dashboard at
the path set in `settings.json` under `ha_views_compare_path`.
