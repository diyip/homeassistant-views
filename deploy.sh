#!/usr/bin/env bash
#
# Deploy all views to www/ and packages/.
# Works from the host or inside the HA Docker container.
#
# For each view directory containing index.html:
#   - Copies index.html  → <ha-root>/www/views/<name>/index.html  (live immediately)
#   - Copies card.yaml   → <ha-root>/packages/views_<name>.yaml   (requires HA restart)
# Never touches data.json, secrets.json, or lib/.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
HA_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

VIEWS_SRC="$SCRIPT_DIR"
VIEWS_WWW="$HA_ROOT/www/views"
PACKAGES="$HA_ROOT/packages"

WWW_OWNER=$(stat -c '%U:%G' "$VIEWS_WWW" 2>/dev/null || echo "")
package_deployed=0

for view_dir in "$VIEWS_SRC"/*/; do
    [[ ! -f "$view_dir/index.html" ]] && continue
    name=$(basename "$view_dir")
    mkdir -p "$VIEWS_WWW/$name"
    cp "$view_dir/index.html" "$VIEWS_WWW/$name/index.html"
    echo "  index.html → live immediately (no restart needed)"
    if [[ -f "$view_dir/card.yaml" ]]; then
        cp "$view_dir/card.yaml" "$PACKAGES/views_${name//-/_}.yaml"
        echo "  card.yaml  → requires HA restart to take effect"
        package_deployed=1
    fi
    [ -n "$WWW_OWNER" ] && chown -R "$WWW_OWNER" "$VIEWS_WWW/$name" 2>/dev/null || true
    echo "deployed: $name"
done

if [[ $package_deployed -eq 1 ]]; then
    echo "Done. Restart HA to load package (card.yaml) changes."
else
    echo "Done. No restart needed."
fi
