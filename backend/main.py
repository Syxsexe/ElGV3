from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from app.database import init_db
from app.routes import (
    auth as auth_route,
    sync as sync_route,
    facturacion as facturacion_route,
    dian as dian_route,
    admin as admin_route,
)

app = FastAPI(
    title="El G POS — Backend DIAN",
    version="0.1.0",
    description="Backend cloud para facturación electrónica DIAN y sincronización con POS desktop",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_route.router)
app.include_router(sync_route.router)
app.include_router(facturacion_route.router)
app.include_router(dian_route.router)
app.include_router(admin_route.router)


@app.on_event("startup")
async def startup():
    await init_db()
    print("✓ Backend ready — Database initialized")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "elg-pos-backend", "environment": settings.dian_environment}
