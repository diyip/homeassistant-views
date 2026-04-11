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
HA automation  ──writes──  update.py  ──reads──  /config/myapp/views/secrets.json
                                       ──reads──  /config/myapp/views/settings.json
```

---

## Directory structure

```
/config/
├── myapp/
│   └── views/
│       ├── README.md
│       ├── secrets.json              ← {"ha_token": "..."}  (gitignored)
│       ├── secrets.example.json      ← template, safe to commit
│       ├── settings.json             ← instance config: ha_url, card params  (gitignored)
│       ├── settings.example.json     ← template, safe to commit
│       ├── deploy.sh                 ← run after adding or editing a view
│       ├── .gitignore
│       ├── lib/
│       │   ├── ha.py                 ← shared HA client utilities (reads secrets + settings)
│       │   └── compare.py            ← shared Playwright utilities (compare scripts)
│       └── <name>/
│           ├── index.html            ← standalone page source
│           ├── update.py             ← fetches entities → writes data.json
│           ├── card.yaml             ← HA shell_command + automation
│           └── compare.py            ← Playwright visual comparison tool
│
└── www/
    ├── echarts.min.js                ← required by energy-usage-graph
    ├── mdi.min.js                    ← required by power-flow-card-plus
    └── views/
        └── <name>/
            ├── index.html            ← deployed by deploy.sh
            └── data.json             ← runtime, written by update.py
```

---

## Instance config files

Both files are **gitignored** — each HA instance maintains its own copies and they are never pushed to git.
Copy from the example templates and fill in instance-specific values.

### `secrets.json`
```json
{"ha_token": "your-long-lived-access-token-here"}
```

### `settings.json`
Contains the HA URL and per-view card configuration. See `settings.example.json` for the full structure.

Key fields:
- `ha_url` — external URL of this HA instance (e.g. `https://myhost.example.com:48131`).
  `lib/ha.py` derives the internal connection URL from this automatically (replaces host with `localhost`,
  keeps scheme and port). Supports both `http` and `https`.
- `ha_views_compare_path` — Lovelace path used by the visual comparison tool.
- `power_flow_card_plus` — full card config block (entities, names, flow parameters).
  `update.py` reads entity IDs from here so nothing is hardcoded in the scripts.

---

## Setup on a new HA instance

### 1. Create a long-lived token

HA → Profile → Long-Lived Access Tokens → Create token.

### 2. Copy this folder into the container

Since the HA config directory is bind-mounted from the host:

```bash
cp -r views /config/myapp/views
```

### 3. Create instance config files

```bash
cd /config/myapp/views
cp secrets.example.json secrets.json
cp settings.example.json settings.json
```

Edit `secrets.json` — paste your token:
```json
{"ha_token": "your-token-here"}
```

Edit `settings.json` — set `ha_url` and update entity IDs for each view.

### 4. Install required static libraries

These files are served at `/local/` and must be placed in `/config/www/`.
Run once per HA instance (inside or outside the container — the www folder is bind-mounted):

```bash
# ECharts — required by energy-usage-graph
curl -fsSL "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js" \
     -o /config/www/echarts.min.js

# MDI icons — required by power-flow-card-plus
curl -fsSL "https://cdn.jsdelivr.net/npm/@mdi/js/mdi.min.js" \
     -o /config/www/mdi.min.js
```

### 5. Deploy

```bash
bash /config/myapp/views/deploy.sh
```

### 6. Restart Home Assistant

Required for HA to load the shell_command and automation from the deployed package files.

### 7. Verify

Open `https://<ha-host>/local/views/<name>/index.html` — the card should show live data within one refresh interval.

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

Captures screenshots of the standalone page and the reference HA card side by side,
for both light and dark themes. Output goes to `~/tmp/views-compare/<name>/`.

Instance config is read from `settings.json` (`ha_url`, `ha_views_compare_path`).
One shared browser session is stored at `~/.config/ha-views/session.json` — save it
once and all views share it.

```bash
cd /config/myapp/views/<name>

python3 compare.py --save-session   # once per HA instance — saves shared session
python3 compare.py                  # → ~/tmp/views-compare/<name>/compare_light.png
                                    #   ~/tmp/views-compare/<name>/compare_dark.png
```

The reference HA cards live at the path set in `settings.json` under
`ha_views_compare_path` (e.g. `dashboard-testing/ha-views`).

Requires: `pip install playwright pillow && playwright install chromium`
