#!/usr/bin/env bash
# Instala el backend El G POS como servicios systemd de USUARIO (rootless podman)
# vía Quadlet, para que arranquen SOLOS al prender el PC del local.
#
# Idempotente: se puede correr varias veces. No usa sudo.
#
#   bash backend/deploy/instalar-autoarranque.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # raíz del repo
DEPLOY="$ROOT/backend/deploy"
QUADLET_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/containers/systemd"

echo "→ Repo: $ROOT"
mkdir -p "$QUADLET_DIR"

# 1) Construir la imagen del backend (la referencian los units).
echo "→ Construyendo imagen del backend (elg-backend-img)…"
podman build -t elg-backend-img -f "$ROOT/backend/Containerfile" "$ROOT/backend"

# 2) Copiar los units Quadlet, sustituyendo la ruta del repo en el backend.
echo "→ Instalando units Quadlet en $QUADLET_DIR"
cp "$DEPLOY/elg.network"           "$QUADLET_DIR/"
cp "$DEPLOY/elg-pgdata.volume"     "$QUADLET_DIR/"
cp "$DEPLOY/elg-postgres.container" "$QUADLET_DIR/"
sed "s#__REPO__#$ROOT#g" "$DEPLOY/elg-backend.container" > "$QUADLET_DIR/elg-backend.container"

# 3) Arranque al boot sin necesidad de iniciar sesión (linger).
echo "→ Habilitando linger para $USER (arranque al prender el PC)…"
loginctl enable-linger "$USER" || echo "  (si falla, córrelo con: sudo loginctl enable-linger $USER)"

# 4) Cargar los units generados por Quadlet e iniciarlos.
echo "→ Recargando systemd de usuario e iniciando servicios…"
systemctl --user daemon-reload
systemctl --user start elg-postgres.service
systemctl --user start elg-backend.service

echo
echo "✓ Listo. Servicios instalados y arrancando al boot."
echo "  Estado:   systemctl --user status elg-backend.service"
echo "  Logs:     podman logs -f elg-backend"
echo "  Salud:    curl http://localhost:8000/health"
echo "  Parar:    systemctl --user stop elg-backend.service elg-postgres.service"
echo "  Quitar:   rm $QUADLET_DIR/elg-*.{container,network,volume}; systemctl --user daemon-reload"
