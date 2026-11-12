# Imagen de la API (pos_api) con las migraciones de la base.
# Se construye desde la raíz del repo:
#   podman build -f deploy/api.Containerfile -t elgv3-api .
# Al arrancar aplica las migraciones pendientes y levanta uvicorn en :8000.
FROM docker.io/library/python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pos_api/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY db/migrar.py db/migrar.py
COPY db/migraciones/ db/migraciones/
COPY pos_api/ pos_api/
COPY deploy/api-entrypoint.sh /usr/local/bin/elg-api

# Sin root dentro del contenedor.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin elg
USER elg

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/elg-api"]
