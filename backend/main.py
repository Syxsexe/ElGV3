import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings, BASE_DIR
from app.database import init_db, async_session

logger = logging.getLogger(__name__)
from app.routes import (
    auth as auth_route,
    sync as sync_route,
    facturacion as facturacion_route,
    dian as dian_route,
    admin as admin_route,
    webhooks as webhooks_route,
)
from app.web.router import router as web_router, templates

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

# API routes
app.include_router(auth_route.router)
app.include_router(sync_route.router)
app.include_router(facturacion_route.router)
app.include_router(dian_route.router)
app.include_router(admin_route.router)
app.include_router(webhooks_route.router)

# Admin web panel
app.include_router(web_router)

# Static files for admin web
static_dir = BASE_DIR / "app" / "web" / "static"
if static_dir.exists():
    app.mount("/admin/static", StaticFiles(directory=str(static_dir)), name="admin_static")


# ── Jinja2 globals ───────────────────────────────────────────────────────

import jinja2


@jinja2.pass_context
def get_flashed_messages(context, with_categories: bool = False):
    """Equivalente estilo Flask: lee los mensajes flash de request.state._flash.
    Los mensajes se guardan como (categoria, mensaje)."""
    request = context.get("request")
    mensajes = getattr(request.state, "_flash", []) if request is not None else []
    if with_categories:
        return mensajes
    return [m for _cat, m in mensajes]


templates.env.globals["get_flashed_messages"] = get_flashed_messages


def _fmt_dt(value):
    """Formatea fechas para las plantillas. Tolera datetime, str o None."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:19]
    try:
        return value.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(value)


templates.env.filters["dt"] = _fmt_dt


_recon_task: asyncio.Task | None = None


async def _reconciliacion_periodica(intervalo: int):
    """Consulta al PT el estado de las facturas pendientes cada `intervalo` seg.
    Imprescindible cuando NO se usa webhook (despliegue local sin URL pública):
    es la única vía para enterarse del veredicto DIAN asíncrono (30 min–2 h)."""
    # Import diferido para no cargar el servicio (y sus deps) al importar main.
    from app.services.factura_service import reconciliar_estados_pendientes
    while True:
        await asyncio.sleep(intervalo)
        try:
            async with async_session() as session:
                r = await reconciliar_estados_pendientes(session)
                if r.get("reconciliadas"):
                    logger.info("Reconciliación DIAN: %s factura(s) actualizada(s): %s",
                                r["reconciliadas"], r.get("detalle"))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # nunca dejar morir el loop por un error puntual
            logger.error("Error en reconciliación periódica: %s", e)


@app.on_event("startup")
async def startup():
    await init_db()
    # Registrar los POS autorizados (POS_CLIENTS del .env) para el login.
    clientes = settings.pos_clients_map
    auth_route.configure_clients(clientes)
    if clientes:
        print(f"✓ {len(clientes)} cliente(s) POS configurado(s): {', '.join(clientes)}")
    else:
        print("⚠ Sin POS_CLIENTS configurados — el login del POS devolverá 401")

    # Job de reconciliación (respaldo/alternativa al webhook).
    global _recon_task
    intervalo = settings.reconciliacion_intervalo_seg
    usa_pt = bool(settings.fe_provider) and settings.fe_provider.lower() != "directo"
    if usa_pt and intervalo > 0:
        _recon_task = asyncio.create_task(_reconciliacion_periodica(intervalo))
        print(f"✓ Reconciliación DIAN periódica activa (cada {intervalo}s)")

    print("✓ Backend ready — Database initialized")


@app.on_event("shutdown")
async def shutdown():
    global _recon_task
    if _recon_task is not None:
        _recon_task.cancel()
        try:
            await _recon_task
        except asyncio.CancelledError:
            pass
        _recon_task = None


@app.get("/health")
async def health():
    return {"status": "ok", "service": "elg-pos-backend", "environment": settings.dian_environment}
