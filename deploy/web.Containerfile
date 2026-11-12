# Imagen de la web: build de Vite servido por Caddy, que además pasa /api/*
# a la API. Se construye desde la raíz del repo:
#   podman build -f deploy/web.Containerfile -t elgv3-web .
FROM docker.io/library/node:24-slim AS build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
# Mismo origen que la web: el navegador llama a /api/... y Caddy lo reenvía.
ENV VITE_API_BASE=/api
RUN npm run build

FROM docker.io/library/caddy:2-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /web/dist /srv
EXPOSE 80
