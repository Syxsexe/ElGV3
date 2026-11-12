# Despliegue del POS en el servidor del local

El servidor (Debian 13, usuario `syxs`, podman sin root) corre tres
contenedores que arrancan solos al prender:

| Contenedor | Qué es | Puerto |
|---|---|---|
| `elg-db` | PostgreSQL 18, datos en el volumen `elg-db` | ninguno (solo la red interna) |
| `elg-api` | La API (`pos_api`); al arrancar aplica las migraciones pendientes | ninguno |
| `elg-web` | Caddy: sirve la web y pasa `/api/*` a la API | **80** |

En el local se entra desde cualquier equipo o celular de la red con
`http://<IP del servidor>/`, y desde fuera con Tailscale.

## Cómo llegan los cambios (CI/CD)

1. Se trabaja en una rama (p. ej. `POSv3`) y se sube. GitHub Actions corre las
   pruebas y el lint/build de la web en cada push
   (`.github/workflows/ci.yml`).
2. Cuando el cambio está listo se une a `main` y se sube. Si las pruebas pasan,
   Actions publica las imágenes `ghcr.io/syxsexe/elgv3-api` y `elgv3-web`
   (etiquetas `latest` y el SHA del commit).
3. En el servidor, a las **2:30 a. m.** se respalda la base y a las **3:00 a. m.**
   `podman-auto-update` descarga las imágenes nuevas y reinicia los
   contenedores. Si la API o la web nuevas no quedan sanas (chequeo de salud),
   podman vuelve solo a la imagen anterior.

Para aplicar un cambio urgente sin esperar a la noche:

```sh
ssh syxs@<servidor> '~/elg/actualizar.sh'        # respalda y actualiza ya
ssh syxs@<servidor> '~/elg/actualizar.sh --ver'  # solo muestra si hay versión nueva
```

Ojo con las migraciones: la API nueva migra la base al arrancar. Si después
falla y podman vuelve a la imagen anterior, la base ya quedó migrada; por eso
las migraciones deben ser compatibles con la versión anterior, y siempre hay
un respaldo de las 2:30.

## Instalación (una sola vez)

Desde el PC de desarrollo, con la carpeta `deploy/` del repo:

```sh
scp -r deploy syxs@<servidor>:~/elg-deploy
ssh -t syxs@<servidor>
cd ~/elg-deploy
sudo ./preparar-root.sh        # puerto 80 para podman sin root + firewall
```

Las imágenes son públicas (como el repo), así que no hace falta login. Si
algún día el repo pasa a privado, el servidor necesitará un token de GitHub
(classic) con solo `read:packages`:
`podman login ghcr.io -u Syxsexe --authfile ~/.config/containers/auth.json`.

```sh
./instalar.sh
podman exec -it elg-api python -m pos_api.configurar   # negocio + primer admin
```

`instalar.sh` se puede repetir (p. ej. si cambian los archivos de `quadlet/` o
`systemd/`): no toca la base ni las claves. Las claves de la base y del JWT se
generan la primera vez en `~/.config/elg/` (`db.env`, `api.env`).

## Respaldos

- Cada noche a las 2:30: `~/elg/respaldos/elg-AAAA-MM-DD_HHMM.dump` (se
  conservan 30 días) y una copia cifrada en Google Drive (180 días) si está
  configurado el remoto `elg-drive` de rclone.
- A mano: `~/elg/respaldo.sh`.
- Restaurar (reemplaza todos los datos; antes hace un respaldo):
  `~/elg/restaurar.sh ~/elg/respaldos/<archivo>.dump`. Uno de Drive se baja
  primero con `rclone copy elg-drive:respaldos/<archivo> ~/elg/respaldos/`.

Configurar Drive (una vez, con `rclone` instalado):

1. Autorizar Google Drive desde el PC, con un túnel para que el navegador
   del PC le responda al servidor:
   `ssh -L 53682:127.0.0.1:53682 syxs@<servidor> 'rclone config create gdrive drive scope=drive.file'`
   y abrir en el PC el enlace `http://127.0.0.1:53682/auth?...` que imprime.
   `drive.file` solo deja ver los archivos que crea rclone.
2. `~/elg/configurar-drive.sh`: crea el remoto cifrado `elg-drive` sobre
   `gdrive:elg-pos` (pide las dos contraseñas sin mostrarlas). **Guárdalas
   fuera del servidor**: sin ellas los respaldos de Drive no se pueden abrir.

## Comandos útiles en el servidor

```sh
systemctl --user status elg-db elg-api elg-web     # estado
journalctl --user -u elg-api -f                    # logs de la API
systemctl --user restart elg-api                   # reiniciar uno
systemctl --user list-timers                       # próximos respaldo y actualización
journalctl --user -u podman-auto-update            # qué pasó en la última actualización
podman exec -it elg-db psql -U elg -d elg          # consola de la base
```
