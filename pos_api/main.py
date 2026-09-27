"""
pos_api/main.py — El G POS, servicio web (piloto Ventas/Cuentas)

Servicio FastAPI SEPARADO del backend DIAN (backend/): no comparte proceso,
puerto ni base de datos. Envuelve modules/ventas.py, cuentas.py y caja.py
(SQLite local) para exponerlos en la red local a celulares/PCs.

Arranque local (dev):
    uvicorn pos_api.main:app --reload --port 8100

Arranque en el servidor:
    ELG_DATA_DIR=/var/lib/elgpos ELG_JWT_SECRET=... ELG_CORS_ORIGINS=http://192.168.1.50:5173 \
        uvicorn pos_api.main:app --host 0.0.0.0 --port 8100
"""
import sqlite3

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import inicializar
from modules.cuentas import migrar as migrar_cuentas
from pos_api.config import CORS_ORIGINS
from pos_api.routers import auth_router, caja_router, cuentas_router, productos_router, ventas_router

app = FastAPI(title="El G POS — API web (piloto Ventas/Cuentas)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(cuentas_router.router)
app.include_router(productos_router.router)
app.include_router(caja_router.router)
app.include_router(ventas_router.router)


@app.on_event("startup")
def startup():
    # Un solo proceso/worker (ver deploy): estas migraciones corren una única
    # vez al arrancar, no por cada request.
    inicializar()
    migrar_cuentas()


@app.exception_handler(ValueError)
def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(PermissionError)
def permission_error_handler(request: Request, exc: PermissionError):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(sqlite3.OperationalError)
def sqlite_locked_handler(request: Request, exc: sqlite3.OperationalError):
    # "database is locked" tras agotar los reintentos de commit_con_reintentos,
    # o cualquier otro error operacional de SQLite. 503 = "reintenta".
    return JSONResponse(status_code=503, content={"detail": "Base de datos ocupada, intenta de nuevo."})


@app.get("/salud")
def salud():
    return {"ok": True}
