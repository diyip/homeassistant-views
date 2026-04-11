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
│   ├── secrets.json              ← {"ha_token": "..."}  (not in git)
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

| View | Refresh | URL | Details |
|---|---|---|---|
| [energy-usage-graph](energy-usage-graph/README.md) | 5 min | `/local/views/energy-usage-graph/index.html` | ECharts hourly bar chart, entities from HA energy config |
| [power-flow-card-plus](power-flow-card-plus/README.md) | 15 s | `/local/views/power-flow-card-plus/index.html` | [power-flow-card-plus](https://github.com/flixlix/power-flow-card-plus) component |

See each view's README for URL parameters, data.json schema, chart implementation details, and visual comparison instructions.

---

## Lovelace iframe card

```yaml
type: iframe
url: http://<ha-host>/local/views/<name>/index.html
aspect_ratio: "75"
```

---

## Visual comparison tool

```bash
cd /config/myapp/views/<name>

python3 compare.py --save-session   # first time — save HA browser session
python3 compare.py                  # headless → standalone.png, ha.png, compare.png
```

Requires: `pip install playwright pillow && playwright install chromium`
