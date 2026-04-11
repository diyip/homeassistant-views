# views

Standalone web pages that embed Home Assistant Lovelace custom cards.
Each page polls live sensor data without requiring a browser login — the HA token stays server-side.

Accessible at: `http://<ha-host>/local/views/<name>/index.html`
Suitable for public monitor displays, iframe embeds, and wall panels.

---

## How it works

```
Browser  ──fetch──▶  /local/views/<name>/data.json   (no auth)
                              ▲
HA automation  ──writes──  update.py  ──reads──  /config/myapp/secrets.json
```

---

## Directory structure

```
/config/
├── myapp/
│   ├── secrets.json              ← {"token": "..."}  (not in git)
│   └── views/
│       ├── README.md
│       ├── deploy.sh             ← run after adding or editing a view
│       ├── .gitignore
│       ├── lib/
│       │   ├── ha.py             ← shared HA client utilities (update scripts)
│       │   └── compare.py        ← shared Playwright utilities (compare scripts)
│       └── <name>/
│           ├── index.html        ← standalone page source
│           ├── update.py         ← fetches entities → writes data.json
│           ├── card.yaml         ← HA shell_command + automation
│           └── compare.py        ← Playwright visual comparison tool
│
└── www/
    └── views/
        └── <name>/
            ├── index.html        ← deployed by deploy.sh
            └── data.json         ← runtime, written by update.py
```

---

## Setup on a new HA instance

### 1. Create a long-lived token

HA → Profile → Long-Lived Access Tokens → Create token.

Save to `/config/myapp/secrets.json`:
```json
{"ha_token": "your-token-here"}
```

### 2. Copy this folder

```bash
cp -r views /config/myapp/views
```

### 3. Deploy

```bash
bash /config/myapp/views/deploy.sh
```

### 4. Restart Home Assistant

Required for HA to load the shell_command and automation from the deployed package files.

### 5. Verify

Open `http://<ha-host>/local/views/<name>/index.html` — the card should show live data within one refresh interval.

---

## Adding a new view

1. Create `<name>/` with four files (copy from an existing view and edit):
   - `index.html` — update entity sensor IDs and chart config
   - `update.py` — update `ENTITIES` / fetch logic and `OUTPUT_FILE` path
   - `card.yaml` — update shell_command name, automation alias/id, script path, and trigger interval
   - `compare.py` — update `STANDALONE_URL`, `HA_URL`, and `HA_SELECTOR`

2. Run `deploy.sh` and restart HA.

---

## Views

| View | Refresh | URL | Notes |
|---|---|---|---|
| power-flow | 15 s | `/local/views/power-flow/index.html` | [power-flow-card-plus](https://github.com/flixlix/power-flow-card-plus) |
| energy-usage-graph | 5 min | `/local/views/energy-usage-graph/index.html` | ECharts bar chart, entities from HA energy config |

---

## energy-usage-graph URL parameters

Entities are derived automatically from HA's Energy configuration — no explicit entity config needed.

| Parameter | Default | Description |
|---|---|---|
| `name` | _(none)_ | Page title shown above chart |

---

## power-flow URL parameters

| Parameter | Default | Description |
|---|---|---|
| `name-grid` | Grid | Grid circle label |
| `name-solar` | Solar | Solar circle label |
| `name-house` | Wit House | House circle label |
| `name-fossil` | Non Fossil | Non-fossil circle label |
| `name` | _(none)_ | Page title shown above card |
| `w_decimals` | 0 | Decimal places for watts |
| `kw_decimals` | 1 | Decimal places for kilowatts |
| `min_flow_rate` | 0.5 | Minimum animation flow rate |
| `max_flow_rate` | 7 | Maximum animation flow rate |
| `max_expected_power` | 5000 | Max power (W) for flow scaling |
| `min_expected_power` | 0.01 | Min power (W) for flow scaling |
| `watt_threshold` | 1000 | W value above which kW is shown |
| `color_icon` | true | Color icons by flow direction |
| `clickable_entities` | true | Enable click on circles |

---

## Lovelace iframe card

```yaml
type: iframe
url: http://<ha-host>/local/views/power-flow/index.html
aspect_ratio: "75"
```

---

## Visual comparison tool

```bash
cd /config/myapp/views/power-flow   # or energy-usage-graph

# First time — save HA browser session
python3 compare.py --save-session

# Normal use (headless)
python3 compare.py
# → standalone.png, ha.png, compare.png
```

Requires: `pip install playwright pillow && playwright install chromium`
