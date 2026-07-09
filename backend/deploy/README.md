# Despliegue local (PC del local) — arranque automático

Modo de operación elegido: **backend + PostgreSQL en el PC del local**, sin
webhook (el veredicto DIAN llega por el job de reconciliación). Costo de
hosting: **$0**. Solo requiere que el backend **arranque solo al prender el PC**.

## Instalación (una vez)

```bash
bash backend/deploy/instalar-autoarranque.sh
```

Esto, con **Podman rootless + Quadlet** (systemd de usuario):

1. Construye la imagen del backend (`elg-backend-img`).
2. Instala los units en `~/.config/containers/systemd/`:
   - `elg.network` → red `elg-net`
   - `elg-pgdata.volume` → **volumen persistente** de Postgres (los datos
     sobreviven a recrear el contenedor)
   - `elg-postgres.container` → PostgreSQL (`Restart=always`)
   - `elg-backend.container` → FastAPI `:8000` (`Restart=always`, arranca
     después de Postgres)
3. Habilita **linger** (`loginctl enable-linger`) para que los servicios
   arranquen al prender el PC **sin necesidad de iniciar sesión**.
4. Arranca los servicios.

## Requisitos previos

- `backend/.env` configurado (FE_PROVIDER=matias, MATIAS_BASE_URL, MATIAS_TOKEN,
  POS_CLIENTS, DATABASE_URL apuntando a `elg-postgres`). Se monta dentro del
  contenedor junto con el repo.
- La primera vez que arranca Postgres nuevo, el backend crea las tablas
  (`init_db`). Luego hay que sembrar la resolución real y correr migraciones:
  ```bash
  podman exec -i elg-postgres psql -U elg -d elg_pos < backend/scripts/seed_resolucion_sandbox.sql
  podman exec -i elg-postgres psql -U elg -d elg_pos < backend/scripts/migracion_estado_error.sql
  ```
  (En producción, la resolución es la REAL habilitada por la DIAN, no la de sandbox.)

## Operación

```bash
systemctl --user status elg-backend.service   # estado
podman logs -f elg-backend                     # logs en vivo
curl http://localhost:8000/health              # salud
systemctl --user restart elg-backend.service   # reiniciar
systemctl --user stop elg-backend.service elg-postgres.service   # parar
```

## Verificar que sobrevive un reinicio

```bash
sudo reboot
# al volver, sin iniciar sesión gráfica siquiera:
curl http://localhost:8000/health   # debe responder {"status":"ok",...}
```

## Desinstalar el auto-arranque

```bash
systemctl --user stop elg-backend.service elg-postgres.service
rm ~/.config/containers/systemd/elg-*.{container,network,volume}
systemctl --user daemon-reload
```

## Nota sobre el webhook

En este modo NO se usa webhook (no hay URL pública). El estado DIAN se actualiza
solo con el **job de reconciliación** del backend (cada
`RECONCILIACION_INTERVALO_SEG` seg, default 600). Si algún día se quiere webhook,
hace falta exponer `:8000` por HTTPS (dominio propio o Cloudflare Tunnel).

## Alternativa rápida (dev, sin systemd)

`bash backend/run_local.sh` levanta lo mismo con `--restart=always` y el volumen
persistente, pero **no** arranca al boot (para eso está la instalación de arriba).
