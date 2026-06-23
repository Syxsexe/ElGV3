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

# Admin web panel
app.include_router(web_router)

# Static files for admin web
static_dir = BASE_DIR / "app" / "web" / "static"
if static_dir.exists():
    app.mount("/admin/static", StaticFiles(directory=str(static_dir)), name="admin_static")


# ── Jinja2 globals ───────────────────────────────────────────────────────

async def flash_message(request: Request):
    """Make flashed messages available in templates."""
    messages = getattr(request.state, "_flash", [])
    return messages


templates.env.globals["get_flashed_messages"] = flash_message


@app.on_event("startup")
async def startup():
    await init_db()
    print("✓ Backend ready — Database initialized")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "elg-pos-backend", "environment": settings.dian_environment}
