#!/usr/bin/env bash
# Respaldo de la base del POS: pg_dump comprimido en ~/elg/respaldos (se
# conservan 30 días) y, si está configurado el remoto de rclone "elg-drive"
# (cifrado), una copia en Google Drive (se conservan 180 días).
#   ~/elg/respaldo.sh            # lo corre elg-respaldo.timer a las 2:30
set -euo pipefail

DIR="$HOME/elg/respaldos"
REMOTO="elg-drive:respaldos"
mkdir -p "$DIR"
archivo="$DIR/elg-$(date +%F_%H%M).dump"

trap 'rm -f "$archivo.tmp"' EXIT   # un volcado a medias no queda suelto
podman exec elg-db pg_dump -U elg -d elg --format=custom >"$archivo.tmp"
mv "$archivo.tmp" "$archivo"
echo "Respaldo local: $archivo ($(du -h "$archivo" | cut -f1))"

find "$DIR" -name 'elg-*.dump' -mtime +30 -delete

if command -v rclone >/dev/null && rclone listremotes 2>/dev/null | grep -qx 'elg-drive:'; then
    rclone copy "$archivo" "$REMOTO"
    rclone delete --min-age 180d "$REMOTO"
    echo "Copia en Drive: $REMOTO/$(basename "$archivo")"
else
    echo "Sin remoto elg-drive en rclone: el respaldo quedó solo en el servidor." >&2
fi
