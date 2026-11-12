#!/bin/sh
# Arranque de la API: espera a Postgres, aplica las migraciones pendientes y
# levanta uvicorn. Si una migración falla, el contenedor no arranca (y la
# actualización automática vuelve a la imagen anterior).
set -eu

: "${ELG_DATABASE_URL:?Falta ELG_DATABASE_URL}"

intentos=0
until python -c "import os, psycopg; psycopg.connect(os.environ['ELG_DATABASE_URL'], connect_timeout=3).close()" 2>/dev/null; do
    intentos=$((intentos + 1))
    if [ "$intentos" -ge 60 ]; then
        echo "Postgres no responde después de 2 minutos." >&2
        exit 1
    fi
    sleep 2
done

DATABASE_URL="$ELG_DATABASE_URL" python db/migrar.py --todo-o-nada

# Detrás de Caddy (misma red de contenedores): se confía en sus cabeceras.
exec uvicorn pos_api.main:app --host 0.0.0.0 --port 8000 \
    --proxy-headers --forwarded-allow-ips '*' --no-server-header
