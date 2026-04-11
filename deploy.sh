#!/usr/bin/env bash
#
# Deploy all views to www/ and packages/.
# Run inside the HA Docker container:
#   bash /config/myapp/views/deploy.sh
#
# For each view directory containing index.html:
#   - Copies index.html  → /config/www/views/<name>/index.html
#   - Copies card.yaml   → /config/packages/views_<name>.yaml
# Restart HA after running to load package changes.
# Never touches data.json, secrets.json, or lib/.

set -euo pipefail

VIEWS_SRC="/config/myapp/views"
VIEWS_WWW="/config/www/views"
PACKAGES="/config/packages"

WWW_OWNER=$(stat -c '%U:%G' "$VIEWS_WWW" 2>/dev/null || echo "")

for view_dir in "$VIEWS_SRC"/*/; do
    [[ ! -f "$view_dir/index.html" ]] && continue
    name=$(basename "$view_dir")
    mkdir -p "$VIEWS_WWW/$name"
    cp "$view_dir/index.html" "$VIEWS_WWW/$name/index.html"
    cp "$view_dir/card.yaml"  "$PACKAGES/views_${name//-/_}.yaml"
    [ -n "$WWW_OWNER" ] && chown -R "$WWW_OWNER" "$VIEWS_WWW/$name" 2>/dev/null || true
    echo "deployed: $name"
done

echo "Done. Restart HA for package changes to take effect."
