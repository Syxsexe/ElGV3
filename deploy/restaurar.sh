#!/usr/bin/env bash
# Restaura la base desde un respaldo (reemplaza TODOS los datos actuales).
#   ~/elg/restaurar.sh ~/elg/respaldos/elg-2026-11-20_0230.dump
# Para uno de Drive, primero: rclone copy elg-drive:respaldos/<archivo> ~/elg/respaldos/
set -euo pipefail

archivo="${1:?Uso: restaurar.sh <archivo .dump>}"
[[ -f "$archivo" ]] || { echo "No existe $archivo" >&2; exit 1; }

read -r -p "Esto reemplaza todos los datos del POS con $archivo. Escribe RESTAURAR para seguir: " ok
[[ "$ok" == "RESTAURAR" ]] || { echo "Cancelado."; exit 1; }

# Copia aparte: el respaldo previo limpia los .dump viejos y podría borrar
# justo el que se va a restaurar.
copia=$(mktemp --suffix=.dump)
cp "$archivo" "$copia"

"$HOME/elg/respaldo.sh"   # por si hay que deshacer la restauración
previo=$(ls -t "$HOME"/elg/respaldos/elg-*.dump | sed -n 1p)

# Pase lo que pase, la API y la web vuelven a arrancar al terminar.
volver() {
    status=$?
    rm -f "$copia"
    systemctl --user start elg-api elg-web || true
    if [[ $status -ne 0 ]]; then
        echo "La restauración falló. Para volver a como estaba: ~/elg/restaurar.sh $previo" >&2
    fi
}
trap volver EXIT

systemctl --user stop elg-web elg-api
podman exec elg-db dropdb -U elg --force elg
podman exec elg-db createdb -U elg elg
podman exec -i elg-db pg_restore -U elg -d elg --no-owner --exit-on-error --single-transaction <"$copia"
echo "Restaurado desde $archivo."
