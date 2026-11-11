"""
pos_api/main.py — El G POS, servicio web

Servicio FastAPI SEPARADO del backend DIAN (backend/): no comparte proceso,
puerto ni base de datos. Usa la base Postgres del POS (esquema de
db/migraciones), que debe estar migrada y configurada antes de arrancar:

    DATABASE_URL=$ELG_DATABASE_URL python db/migrar.py
    python -m pos_api.configurar          # solo la primera vez

Arranque local (dev):
    ELG_DATABASE_URL=postgresql://elg:elg@localhost:5433/elg \
        uvicorn pos_api.main:app --reload --port 8100

Arranque en el servidor:
    ELG_DATABASE_URL=... ELG_JWT_SECRET=... ELG_CORS_ORIGINS=http://192.168.1.50:5173 \
        uvicorn pos_api.main:app --host 0.0.0.0 --port 8100
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pos_api import errores
from pos_api.config import CORS_ORIGINS, DATABASE_URL
from pos_api.db import abrir_pool, cerrar_pool, migraciones_pendientes
from pos_api.routers import (auditoria_router, auth_router, caja_router, catalogo_router, configuracion_router,
                             compras_router, credito_router, documentos_router, terceros_router, torneos_router,
                             reportes_router, usuarios_router, ventas_router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DATABASE_URL:
        raise RuntimeError("Falta ELG_DATABASE_URL (ej. postgresql://elg:elg@localhost:5433/elg).")
    pendientes = migraciones_pendientes(DATABASE_URL)
    if pendientes:
        raise RuntimeError(f"La base tiene migraciones pendientes ({', '.join(pendientes)}): corre db/migrar.py.")
    abrir_pool(DATABASE_URL)
    try:
        yield
    finally:
        cerrar_pool()


app = FastAPI(title="El G POS — API web", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

errores.registrar(app)
app.include_router(auth_router.router)
app.include_router(usuarios_router.router)
app.include_router(configuracion_router.router)
app.include_router(auditoria_router.router)
app.include_router(catalogo_router.router)
app.include_router(terceros_router.router)
app.include_router(caja_router.router)
app.include_router(ventas_router.router)
app.include_router(credito_router.router)
app.include_router(compras_router.router)
app.include_router(torneos_router.router)
app.include_router(documentos_router.router)
app.include_router(reportes_router.router)


@app.get("/salud")
def salud():
    return {"ok": True}
