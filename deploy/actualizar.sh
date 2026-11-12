#!/usr/bin/env bash
# Actualiza ya mismo (sin esperar a las 3:00 a. m.) a las imágenes más nuevas
# publicadas por GitHub Actions. Antes hace un respaldo de la base.
#   ~/elg/actualizar.sh           # aplica
#   ~/elg/actualizar.sh --ver     # solo muestra si hay versión nueva
set -euo pipefail
export REGISTRY_AUTH_FILE="$HOME/.config/containers/auth.json"

if [[ "${1:-}" == "--ver" ]]; then
    exec podman auto-update --dry-run
fi
"$HOME/elg/respaldo.sh"
podman auto-update
podman image prune -f >/dev/null
for u in elg-db elg-api elg-web; do
    printf '%-8s %s\n' "$u" "$(systemctl --user is-active "$u" || true)"
done
