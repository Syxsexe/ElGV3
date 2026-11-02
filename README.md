# El G — POS web

Punto de venta de **El G** (tienda de TCG, juegos de mesa y comidas rápidas) en
versión web, para usarlo desde celulares y PCs en la red local del negocio.

La app de escritorio (Tkinter) quedó fuera de esta rama; sigue en el historial
de git hasta el commit anterior a la limpieza.

## Estructura

| Carpeta / archivo | Qué es |
|---|---|
| `web/` | Frontend React + Vite (Ventas, Cuentas, Caja) |
| `pos_api/` | API FastAPI que usa el frontend (puerto 8100) |
| `database.py`, `auth.py`, `paths.py`, `modules/` | Lógica de negocio y acceso a SQLite que envuelve `pos_api` |
| `backend/` | Servicio de facturación electrónica DIAN (FastAPI + Postgres, adaptador Matias) |
| `tests/` | Pruebas del backend DIAN (CUFE, QR, XML UBL 2.1, servidor mock) |

## Desarrollo

API (desde la raíz del repo):

```bash
python -m venv .venv
.venv/bin/pip install -r pos_api/requirements.txt
.venv/bin/uvicorn pos_api.main:app --reload --port 8100
```

Variables de entorno: `ELG_DATA_DIR` (carpeta de la base SQLite), `ELG_JWT_SECRET`,
`ELG_JWT_EXP_HORAS` y `ELG_CORS_ORIGINS`.

Frontend:

```bash
cd web
npm install
VITE_API_BASE=http://localhost:8100 npm run dev
```

Pruebas del backend DIAN:

```bash
.venv/bin/pip install -r requirements-test.txt
.venv/bin/python -m pytest tests
```

## Base de datos Postgres (`db/`)

El modelo relacional nuevo (59 tablas, Postgres 18) vive en `db/migraciones/`
como archivos SQL numerados. Todavía no lo usa la API: `pos_api` sigue sobre
SQLite hasta la migración de datos.

```bash
db/pg_local.sh                                   # Postgres 18 en podman, puerto 5433
.venv/bin/pip install -r db/requirements.txt
export DATABASE_URL=postgresql://elg:elg@localhost:5433/elg
.venv/bin/python db/migrar.py                    # aplica las migraciones pendientes
```

Pruebas del esquema (crean y borran una base desechable):

```bash
PRUEBAS_DATABASE_URL=postgresql://elg:elg@localhost:5433/elg .venv/bin/python -m pytest db/pruebas
```

Sin `PRUEBAS_DATABASE_URL` esas pruebas se omiten. `db/migraciones/0014_divipola.sql`
se genera con `db/datos/generar_divipola.py` desde el CSV oficial del DANE.

## Estado

- Migrados a web: Ventas, Cuentas (mesas) y Caja (apertura, cierre, historial).
- Modelo relacional nuevo en Postgres: esquema listo (`db/`); falta migrar los datos y adaptar la API.
