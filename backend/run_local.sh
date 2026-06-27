#!/usr/bin/env bash
# Levanta el backend El G POS localmente con Podman (Postgres + backend + mock DIAN).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NET=elg-net
PG=elg-postgres
BE=elg-backend
IMG=elg-backend-img

echo "→ Red Podman ($NET)"
podman network exists "$NET" || podman network create "$NET"

echo "→ PostgreSQL ($PG)"
if podman container exists "$PG"; then
  podman start "$PG" >/dev/null
else
  podman run -d --name "$PG" --network "$NET" \
    -e POSTGRES_USER=elg -e POSTGRES_PASSWORD=elg -e POSTGRES_DB=elg_pos \
    -p 5432:5432 docker.io/library/postgres:16 >/dev/null
fi

echo "→ Construyendo imagen backend ($IMG)"
podman build -t "$IMG" -f "$ROOT/backend/Containerfile" "$ROOT/backend"

echo "→ Backend ($BE)"
podman rm -f "$BE" >/dev/null 2>&1 || true
podman run -d --name "$BE" --network "$NET" \
  -p 8000:8000 \
  -v "$ROOT":/app:z \
  "$IMG" >/dev/null

echo
echo "✓ Backend levantado."
echo "  Salud:  http://localhost:8000/health"
echo "  Admin:  http://localhost:8000/admin   (admin / admin123)"
echo "  Logs:   podman logs -f $BE"
echo "  Parar:  backend/stop_local.sh"
