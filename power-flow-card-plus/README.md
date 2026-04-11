# power-flow-card-plus

Standalone real-time power flow card built on the
[power-flow-card-plus](https://github.com/flixlix/power-flow-card-plus)
Lovelace component. Displays live grid, solar, and home power values with
animated flow lines — without requiring a browser login.

Served at: `/local/views/power-flow-card-plus/index.html`

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

All parameters are optional. Numeric and boolean values override the corresponding
fields in `settings.json`; entity name overrides apply to the matching entity's
`name` field. Defaults are whatever is set in `settings.json`.

| Parameter | Overrides | Description |
|---|---|---|
| `name` | _(page title only)_ | Page title shown above card; also sets `document.title` |
| `name-grid` | `entities.grid.name` | Grid circle label |
| `name-solar` | `entities.solar.name` | Solar circle label |
| `name-house` | `entities.home.name` | House circle label |
| `name-fossil` | `entities.fossil_fuel_percentage.name` | Non-fossil circle label |
| `w_decimals` | `w_decimals` | Decimal places when displaying watts |
| `kw_decimals` | `kw_decimals` | Decimal places when displaying kilowatts |
| `min_flow_rate` | `min_flow_rate` | Minimum animation flow rate |
| `max_flow_rate` | `max_flow_rate` | Maximum animation flow rate |
| `max_expected_power` | `max_expected_power` | Max power (W) for flow speed scaling |
| `min_expected_power` | `min_expected_power` | Min power (W) for flow speed scaling |
| `watt_threshold` | `watt_threshold` | W value above which kW display is used |
| `color_icon` | `color_icon` | Color circle icons by flow direction |
| `clickable_entities` | `clickable_entities` | Enable tap/click on circles |

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
