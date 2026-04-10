#!/usr/bin/env bash
# Deploy all views — run inside the HA docker container:
#   bash /config/myapp/views/deploy.sh
# Copies index.html → www/views/<name>/ and card.yaml → packages/views_<name>.yaml
# Restart HA after running to load package changes. Never touches data.json or secrets.json.

set -euo pipefail

VIEWS_SRC="/config/myapp/views"
VIEWS_WWW="/config/www/views"
PACKAGES="/config/packages"

for view_dir in "$VIEWS_SRC"/*/; do
    name=$(basename "$view_dir")
    mkdir -p "$VIEWS_WWW/$name"
    cp "$view_dir/index.html" "$VIEWS_WWW/$name/index.html"
    cp "$view_dir/card.yaml"  "$PACKAGES/views_${name//-/_}.yaml"
    echo "deployed: $name"
done

echo "done. Restart HA for package changes to take effect."
