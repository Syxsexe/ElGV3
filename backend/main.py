from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings, BASE_DIR
from app.database import init_db
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
    print("✓ Backend ready — Database initialized")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "elg-pos-backend", "environment": settings.dian_environment}
