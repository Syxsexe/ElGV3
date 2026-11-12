#!/usr/bin/env bash
# Instala (o reinstala) el POS en el servidor, como el usuario normal (sin
# sudo). Se corre desde esta carpeta deploy/ copiada al servidor:
#   ./instalar.sh
# Es seguro repetirlo: no toca la base ni las claves que ya existan.
# Antes, una sola vez: sudo ./preparar-root.sh (y el login en ghcr.io solo si
# las imágenes son privadas; ver README).
set -euo pipefail
cd "$(dirname "$0")"

CONF="$HOME/.config/elg"
QUADLETS="$HOME/.config/containers/systemd"
UNIDADES="$HOME/.config/systemd/user"
export REGISTRY_AUTH_FILE="$HOME/.config/containers/auth.json"

# n bytes al azar en hexadecimal (2n caracteres, seguros en URLs y .env).
aleatorio() { od -An -tx1 -N"$1" /dev/urandom | tr -d ' \n'; }

# 1. Claves: se generan la primera vez y nunca se cambian solas.
mkdir -p "$CONF"
chmod 700 "$CONF"
if [[ ! -f "$CONF/db.env" ]]; then
    clave_db=$(aleatorio 24)
    umask 077
    printf 'POSTGRES_USER=elg\nPOSTGRES_PASSWORD=%s\nPOSTGRES_DB=elg\n' "$clave_db" >"$CONF/db.env"
    printf 'ELG_DATABASE_URL=postgresql://elg:%s@elg-db:5432/elg\nELG_JWT_SECRET=%s\nELG_CORS_ORIGINS=http://localhost\n' \
        "$clave_db" "$(aleatorio 32)" >"$CONF/api.env"
    umask 022
    echo "✓ Claves nuevas en $CONF"
fi

# Credenciales de ghcr.io: con el repo público no hacen falta, pero los
# servicios apuntan a este archivo y podman falla si no existe.
if [[ ! -f "$REGISTRY_AUTH_FILE" ]]; then
    mkdir -p "$(dirname "$REGISTRY_AUTH_FILE")"
    (umask 077; echo '{"auths": {}}' >"$REGISTRY_AUTH_FILE")
fi

# 2. Servicios (quadlets), temporizadores y scripts.
mkdir -p "$QUADLETS" "$UNIDADES/podman-auto-update.timer.d" "$UNIDADES/podman-auto-update.service.d" "$HOME/elg"
cp quadlet/* "$QUADLETS/"
cp systemd/elg-respaldo.service systemd/elg-respaldo.timer "$UNIDADES/"
cp systemd/podman-auto-update.timer.d-elg.conf "$UNIDADES/podman-auto-update.timer.d/elg.conf"
cp systemd/podman-auto-update.service.d-elg.conf "$UNIDADES/podman-auto-update.service.d/elg.conf"
install -m 755 respaldo.sh actualizar.sh restaurar.sh configurar-drive.sh "$HOME/elg/"
echo "✓ Servicios copiados"

# 3. Imágenes (la primera vez tardan) y arranque.
podman pull -q docker.io/library/postgres:18 ghcr.io/syxsexe/elgv3-api:latest ghcr.io/syxsexe/elgv3-web:latest >/dev/null
systemctl --user daemon-reload
# restart (no start): si cambiaron los quadlets, los que ya corrían los toman.
systemctl --user restart elg-db elg-api elg-web
systemctl --user enable --now podman-auto-update.timer elg-respaldo.timer
echo "✓ POS en marcha"

systemctl --user --no-pager list-timers podman-auto-update.timer elg-respaldo.timer
if ! podman exec elg-db psql -U elg -d elg -tAc 'SELECT 1 FROM usuarios LIMIT 1' | grep -q 1; then
    echo
    echo "La base está vacía. Configura el negocio y el primer administrador con:"
    echo "  podman exec -it elg-api python -m pos_api.configurar"
fi
