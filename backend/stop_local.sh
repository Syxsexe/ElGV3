#!/usr/bin/env bash
# Detiene y elimina los contenedores del backend local.
set -uo pipefail
podman rm -f elg-backend  2>/dev/null || true
podman stop  elg-postgres 2>/dev/null || true
echo "✓ Backend detenido (Postgres conserva sus datos; usa 'podman rm elg-postgres' para borrarlos)."
