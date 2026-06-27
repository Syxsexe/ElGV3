#!/usr/bin/env bash
# Arranque del contenedor backend: espera a Postgres, lanza el mock DIAN y uvicorn.
set -e
cd /app/backend

echo "⏳ Esperando a PostgreSQL (elg-postgres:5432)..."
until python -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('elg-postgres',5432)); s.close()" 2>/dev/null; do
  sleep 1
done
echo "✓ PostgreSQL accesible"

echo "▶ Mock DIAN en :8081"
python run_mock_dian.py --port 8081 --delay 0.1 &

echo "▶ Backend en :8000"
exec uvicorn main:app --host 0.0.0.0 --port 8000
