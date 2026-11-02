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

## Estado

- Migrados a web: Ventas, Cuentas (mesas) y Caja (apertura, cierre, historial).
- En diseño: nuevo modelo relacional para pasar de SQLite a Postgres.
