# power-flow-card-plus

Standalone real-time power flow card built on the
[power-flow-card-plus](https://github.com/flixlix/power-flow-card-plus)
Lovelace component. Displays live grid, solar, and home power values with
animated flow lines — without requiring a browser login.

Served at: `/local/views/power-flow-card-plus/index.html`

---

## Common use cases

All parameters are optional and can be combined freely. Values are
auto-coerced: `true`/`false` → boolean, numeric strings → number.

### Passing any card parameter

The URL param system is **not limited to the examples below**. Any configuration
key supported by the card can be passed as a URL parameter — top-level, named
entity, or individual entity.

For the full list of available parameters, refer to the card's documentation:
[github.com/flixlix/power-flow-card-plus](https://github.com/flixlix/power-flow-card-plus)

**How to translate a card config key to a URL param:**

| Card config (`settings.json`) | URL parameter |
|---|---|
| `"kw_decimals": 2` (top-level) | `?kw_decimals=2` |
| `"solar": { "name": "PV" }` | `?solar_name=PV` |
| `"solar": { "display_zero": true }` | `?solar_display_zero=true` |
| `"individual": [{ "name": "EV" }]` | `?individual_0_name=EV` |
| `"individual": [{ "color_icon": false }]` | `?individual_0_color_icon=false` |

Any key not recognised as a named-entity or individual override is applied
directly to the root card config — so new parameters from future card versions
work without any code changes.

### 1. Default — no parameters

```
https://yit.yipintsoi.net:48131/local/views/power-flow-card-plus/index.html
```

Loads with all defaults from `settings.json`.

---

### 2. Add a page title

```
https://yit.yipintsoi.net:48131/local/views/power-flow-card-plus/index.html?name=Car+Park+B1
```

Shows "CAR PARK B1" above the card and sets the browser tab title.

---

### 3. Rename labels

```
https://yit.yipintsoi.net:48131/local/views/power-flow-card-plus/index.html?grid_name=Mains&solar_name=Rooftop+PV&home_name=Building+A&individual_0_name=EV+Chargers
```

Renames all four circles without touching `settings.json`.

---

### 4. Change icons

```
https://yit.yipintsoi.net:48131/local/views/power-flow-card-plus/index.html?solar_icon=mdi:solar-panel&individual_0_icon=mdi:car-electric
```

Overrides icons using any MDI icon name (`mdi:*`). Works for named entities
(`grid`, `solar`, `home`) and individual entities by index.

---

### 5. Higher precision display

```
https://yit.yipintsoi.net:48131/local/views/power-flow-card-plus/index.html?kw_decimals=2
```

Shows kilowatt values to 2 decimal places instead of the default 1.

---

### 6. Calm wall display

```
https://yit.yipintsoi.net:48131/local/views/power-flow-card-plus/index.html?kw_decimals=0&max_flow_rate=2
```

Rounds kW values to whole numbers and slows flow animations — good for a
monitor that people glance at rather than read closely.

---

### 7. Full combination

```
https://yit.yipintsoi.net:48131/local/views/power-flow-card-plus/index.html?name=Car+Park+B1&grid_name=Mains&solar_name=Rooftop+PV&home_name=Building+A&solar_icon=mdi:solar-panel&individual_0_name=EV+Chargers&individual_0_icon=mdi:car-electric&kw_decimals=2&max_flow_rate=3
```

Title, renamed labels, custom icons, precision, and animation speed — all combined.

---

## How it works

```
HA REST API  /api/states
        │
        ▼
  update.py  ──writes──  data.json  ──fetch──  index.html
                                                  │
                                       card.hass = { states, ... }
                                                  │
                                       power-flow-card-plus (renders)
```

`update.py` runs inside the HA container every 15 seconds via shell_command.
`index.html` polls `data.json` every 15 seconds and pushes new state into
the card's `hass` property — no page reload needed.

---

## Data flow detail

### 1. State fetch (`/api/states`)

`update.py` fetches all HA entity states and filters to the configured
`ENTITIES` set. The full HA state objects are written as-is to `data.json`
so `index.html` can pass them directly to the card.

### 2. Rendering

`power-flow-card-plus` is a standard HA Lovelace web component. Outside of
HA it has no `hass` object, no custom element registry stubs, and no MDI
icons. `index.html` provides all of these:

#### HA custom element stubs

| Element | Stub behaviour |
|---|---|
| `hui-card` | `display: block` |
| `ha-card` | `display: block; overflow: hidden` |
| `ha-ripple` | `display: none` (suppresses click ripple) |
| `ha-svg-icon` | shadow DOM SVG rendered from `path` property/attribute |
| `ha-icon` | shadow DOM SVG rendered via `mdiPath()` lookup in `mdi.min.js` |

#### MDI icon resolution

`/local/mdi.min.js` exports all Material Design Icon path strings as named
ES module exports. Icon names (`mdi:flash`) are converted to camelCase keys
(`mdiFlash`) and looked up at render time.

#### `hass` mock object

The card reads from `card.hass` on every refresh:

```javascript
card.hass = {
  states,                          // entity_id → full HA state object
  localize: (key) => ...,          // returns the last segment, spaces for underscores
  locale:   { language: "th", number_format: "decimal_dot", ... },
  config:   { unit_system: { power: "W", energy: "kWh", ... },
              currency: "THB", country: "TH", time_zone: "Asia/Bangkok" },
  user:     { is_admin: false, name: "monitor" },
  themes:   { darkMode: dark, theme: "default" },
  selectedTheme: { dark: dark },
  connected: true,
  callService: () => Promise.resolve(),
  callApi:     () => Promise.resolve(),
}
```

`darkMode` is read from `window.matchMedia('prefers-color-scheme: dark')`
on every refresh so the card tracks system theme changes without reload.

#### CSS patches

After the card's first render, a `CSSStyleSheet` is injected into
`card.shadowRoot.adoptedStyleSheets` to fix spacing:

```css
.card-content { padding: 16px }
.circle-container.grid .label,
.circle-container.home .label { margin-top: 4px }
```

---

## Entities and card config

All entity IDs and card parameters are configured in **`settings.json`** under the
`power_flow_card_plus` key — nothing is hardcoded in `update.py` or `index.html`.

`update.py` reads entity IDs from `settings.json`, fetches their states, and writes
`data.json` with both the state objects and a `_config` key containing the full card
config. `index.html` reads `_config` from `data.json` at load time and passes it
directly to `card.setConfig()`.

To change entities or card parameters, edit `settings.json` and wait for the next
`update.py` run (≤ 15 s) — no redeploy needed.

---

## data.json schema

Written to `/config/www/views/power-flow-card-plus/data.json`.

The file contains the card config plus a flat map of `entity_id → HA state object`:

```json
{
  "_config": { "entities": { "grid": { "entity": "sensor.xxx", ... }, ... }, ... },
  "sensor.xxx": {
    "entity_id": "sensor.xxx",
    "state": "1234",
    "attributes": { "unit_of_measurement": "kW", "friendly_name": "Grid", ... },
    "last_changed": "2026-04-11T09:00:00+00:00",
    "last_updated": "2026-04-11T09:00:00+00:00"
  },
  ...
}
```

`_config` is the `power_flow_card_plus` block from `settings.json`, embedded by
`update.py` so `index.html` can call `card.setConfig()` without reading the file
directly (which is not served under `/local/`).

On error: `{"_error": "message"}` — refresh is silently skipped, last
valid state remains displayed.

---

## URL parameters

All parameters are optional. Defaults come from `settings.json` via `data.json`.

Values are automatically coerced to the right JS type:
- `"true"` / `"false"` → boolean
- numeric strings → number
- everything else → string

**Priority:** URL parameters always override `settings.json` values.

**Forward compatibility:** Any parameter key not explicitly handled is passed
directly to the card config as a top-level key. This means new parameters
introduced in future card versions work without any code changes — just add
them to the URL.

---

### Page title — `name=...`

Sets the label shown above the card and the browser tab title.

```
?name=Power+Flow
?name=Car+Park+B1
```

---

### Top-level card overrides — `key=value`

Apply directly to the root card config object.

| Parameter | Default | Description |
|---|---|---|
| `w_decimals` | `0` | Decimal places for watt values |
| `kw_decimals` | `1` | Decimal places for kilowatt values |
| `min_flow_rate` | `0.5` | Slowest flow animation speed |
| `max_flow_rate` | `7` | Fastest flow animation speed |
| `max_expected_power` | `250000` | Power (W) at which flow runs at max speed |
| `min_expected_power` | `10000` | Power (W) at which flow runs at min speed |
| `watt_threshold` | `1000` | Switch from W to kW display above this value |
| `display_zero_lines` | `false` | Show flow lines even when value is 0 |

**Common examples:**

```
# Show more decimal places
?kw_decimals=2

# Show flow lines at zero (useful for monitoring idle state)
?display_zero_lines=true

# Slow down animations for a calmer display
?max_flow_rate=3

# Switch to kW earlier (e.g. for a high-power site)
?watt_threshold=500

# Combine multiple overrides
?kw_decimals=2&display_zero_lines=true&max_flow_rate=3
```

---

### Named entity overrides — `entityname_key=value`

Override any field of a named entity. Prefix the key with the entity name and `_`.

Named entities: `grid`, `solar`, `home`, `fossil_fuel_percentage`

| Example | Effect |
|---|---|
| `?grid_name=Mains` | Rename grid label |
| `?solar_name=PV+Roof` | Rename solar label |
| `?home_name=Office` | Rename home label |
| `?solar_display_zero=true` | Show solar circle even at 0 W |
| `?grid_display_zero_tolerance=100` | Treat grid < 100 W as zero |
| `?fossil_fuel_percentage_color_icon=false` | Disable colour icon for non-fossil |

**Common examples:**

```
# Rename labels for a specific location
?grid_name=Mains&solar_name=Rooftop+PV&home_name=Building+A

# Keep solar circle visible even at night
?solar_display_zero=true

# Combine with a page title
?name=Building+A&grid_name=Mains&solar_name=Rooftop+PV
```

---

### Individual entity overrides — `individual_N_key=value`

Override any field of an individual entity. Index `N` is 0-based, matching the
order of the `individual` array in `settings.json`.

| Example | Effect |
|---|---|
| `?individual_0_name=EV` | Rename first individual label |
| `?individual_0_color_icon=false` | Disable colour icon for first individual |
| `?individual_0_display_zero=true` | Show first individual even at 0 W |
| `?individual_1_name=HVAC` | Rename second individual label |

**Common examples:**

```
# Rename individual devices
?individual_0_name=EV+Chargers&individual_1_name=HVAC

# Show all individuals even at zero (useful for monitoring)
?individual_0_display_zero=true&individual_1_display_zero=true
```

> **Note:** `display_zero: false` for individual entities does not hide the
> circle in power-flow-card-plus v0.3.2 — this is a card limitation.

---

### Full example URL

```
https://<ha-host>/local/views/power-flow-card-plus/index.html
  ?name=Car+Park+B1
  &kw_decimals=2
  &display_zero_lines=true
  &solar_name=Rooftop+PV
  &solar_display_zero=true
  &individual_0_name=EV+Chargers
  &individual_0_display_zero=true
```

(Line breaks added for readability — use as a single URL.)

---

## Refresh schedule

| Component | Interval | Mechanism |
|---|---|---|
| `update.py` | 15 seconds | HA `time_pattern` automation (`seconds: "/15"`) |
| `index.html` | 15 seconds | `setInterval(refresh, 15000)` |

---

## Local files required

| Path | Purpose |
|---|---|
| `/local/mdi.min.js` | Material Design Icons path data (ES module) |
| `/local/community/power-flow-card-plus/power-flow-card-plus.js` | The card component |

The card JS is loaded with a cache-bust version query (`?v=8`). Increment
this when updating the component to force browsers to reload it.

---

## Visual comparison

```bash
cd /config/myapp/views/power-flow-card-plus

python3 compare.py --save-session   # once per HA instance — saves shared session
python3 compare.py                  # → ~/tmp/views-compare/power-flow-card-plus/compare_light.png
                                    #   ~/tmp/views-compare/power-flow-card-plus/compare_dark.png
```

Instance config (`ha_url`, `ha_views_compare_path`) is read from `settings.json`.
The shared session lives at `~/.config/ha-views/session.json` — one session for all views.
The reference `power-flow-card-plus` card must be present on the dashboard at
the path set in `settings.json` under `ha_views_compare_path`.
