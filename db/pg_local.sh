#!/usr/bin/env bash
# Levanta Postgres 18 local en podman para desarrollo del POS web.
# Usa el puerto 5433 para no chocar con el Postgres 16 del backend DIAN (5432).
#
#   db/pg_local.sh            arranca (o crea) el contenedor
#   db/pg_local.sh --reset    lo borra con sus datos y lo crea de nuevo
#
# Luego:  export DATABASE_URL=postgresql://elg:elg@localhost:5433/elg
set -euo pipefail

CONTENEDOR=elg-pos-pg18
VOLUMEN=elg-pos-pg18-data
IMAGEN=docker.io/library/postgres:18

if [[ "${1:-}" == "--reset" ]]; then
  podman rm -f "$CONTENEDOR" >/dev/null 2>&1 || true
  podman volume rm -f "$VOLUMEN" >/dev/null 2>&1 || true
fi

if podman container exists "$CONTENEDOR"; then
  podman start "$CONTENEDOR" >/dev/null
else
  podman run -d --name "$CONTENEDOR" \
    -e POSTGRES_USER=elg -e POSTGRES_PASSWORD=elg -e POSTGRES_DB=elg \
    -e TZ=America/Bogota -e PGTZ=America/Bogota \
    -v "$VOLUMEN":/var/lib/postgresql \
    -p 5433:5432 "$IMAGEN" >/dev/null
fi

echo -n "Esperando a Postgres"
until podman exec "$CONTENEDOR" pg_isready -U elg -d elg >/dev/null 2>&1; do
  echo -n "."; sleep 1
done
echo " listo: postgresql://elg:elg@localhost:5433/elg"
