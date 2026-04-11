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

## Entities

Defined in two places that must stay in sync:

| File | Location |
|---|---|
| `update.py` | `ENTITIES` frozenset |
| `index.html` | `card.setConfig({ entities: { ... } })` |

Current entities:

| Role | Entity ID |
|---|---|
| Grid | `sensor.wit_grid_w` |
| Solar | `sensor.wit_solar_w` |
| Home | `sensor.wit_house_kw` |
| Non-fossil % | `sensor.electricity_maps_grid_fossil_fuel_percentage` |

To change entities, update both files and redeploy.

---

## data.json schema

Written to `/config/www/views/power-flow-card-plus/data.json`.

The file contains a flat map of `entity_id → HA state object`:

```json
{
  "sensor.wit_grid_w": {
    "entity_id": "sensor.wit_grid_w",
    "state": "1234",
    "attributes": { "unit_of_measurement": "W", "friendly_name": "Grid", ... },
    "last_changed": "2026-04-11T09:00:00+00:00",
    "last_updated": "2026-04-11T09:00:00+00:00"
  },
  ...
}
```

On error: `{"_error": "message"}` — refresh is silently skipped, last
valid state remains displayed.

---

## URL parameters

All parameters are optional. Defaults match the installed HA Lovelace card config.

| Parameter | Default | Description |
|---|---|---|
| `name` | _(none)_ | Page title shown above card; also sets `document.title` |
| `name-grid` | Grid | Grid circle label |
| `name-solar` | Solar | Solar circle label |
| `name-house` | Wit House | House circle label |
| `name-fossil` | Non Fossil | Non-fossil circle label |
| `w_decimals` | 0 | Decimal places when displaying watts |
| `kw_decimals` | 1 | Decimal places when displaying kilowatts |
| `min_flow_rate` | 0.5 | Minimum animation flow rate |
| `max_flow_rate` | 7 | Maximum animation flow rate |
| `max_expected_power` | 5000 | Max power (W) used for flow speed scaling |
| `min_expected_power` | 0.01 | Min power (W) used for flow speed scaling |
| `watt_threshold` | 1000 | W value above which kW display is used |
| `color_icon` | true | Color circle icons by flow direction |
| `clickable_entities` | true | Enable tap/click on circles |

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

python3 compare.py --save-session   # first time only
python3 compare.py                  # → standalone.png, ha.png, compare.png
```

`HA_URL` points to the lovelace dashboard containing the reference
`power-flow-card-plus` card. Update `compare.py` if the dashboard URL changes.
