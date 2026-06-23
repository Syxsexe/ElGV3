"""
app/web/router.py — Admin web panel routes.
"""
import uuid
import json
from datetime import date, datetime
from pathlib import Path

from fastapi import (
    APIRouter, Request, Depends, HTTPException, UploadFile, File, Form,
)
from fastapi.responses import (
    HTMLResponse, RedirectResponse, JSONResponse,
)
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.routes.auth import require_auth
from app.models import Factura, Resolucion, SyncLog
from config import settings, BASE_DIR

router = APIRouter(prefix="/admin", tags=["admin_web"])

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "web" / "templates"))

STATIC_DIR = BASE_DIR / "app" / "web" / "static"
if STATIC_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    # mounted in main.py via .mount()

# ── Auth helpers ──────────────────────────────────────────────────────────

# Simple admin session stored in a dict keyed by a session token
_admin_sessions: dict[str, str] = {}
_admin_token_cookie = "elg_admin_token"


def _get_admin_user(request: Request) -> str | None:
    token = request.cookies.get(_admin_token_cookie)
    if token and token in _admin_sessions:
        return _admin_sessions[token]
    return None


def _require_admin(request: Request):
    user = _get_admin_user(request)
    if not user:
        raise HTTPException(status_code=303, detail="Unauthorized")
    return user


def _flash(request: Request, message: str, category: str = "success"):
    if not hasattr(request.state, "_flash"):
        request.state._flash = []
    request.state._flash.append((category, message))


# ── Login / Logout ───────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = _get_admin_user(request)
    if user:
        return RedirectResponse("/admin/", status_code=302)
    return templates.TemplateResponse(
        "login.html", {"request": request, "hide_sidebar": True}
    )


@router.post("/login")
async def login_submit(request: Request):
    from auth import iniciar_sesion

    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")

    session = iniciar_sesion(username, password)
    if not session or session.get("rol") != "admin":
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "hide_sidebar": True,
                "error": "Credenciales inválidas o no tienes permisos de admin",
            },
        )

    token = str(uuid.uuid4())
    _admin_sessions[token] = username

    resp = RedirectResponse("/admin/", status_code=302)
    resp.set_cookie(key=_admin_token_cookie, value=token, httponly=True, max_age=86400)
    return resp


@router.get("/logout")
async def logout(request: Request):
    token = request.cookies.get(_admin_token_cookie)
    if token and token in _admin_sessions:
        del _admin_sessions[token]
    resp = RedirectResponse("/admin/login", status_code=302)
    resp.delete_cookie(_admin_token_cookie)
    return resp


# ── Dashboard ────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: AsyncSession = Depends(get_session)):
    user = _require_admin(request)

    total = (await session.execute(select(func.count(Factura.id)))).scalar() or 0
    aceptadas = (
        await session.execute(
            select(func.count(Factura.id)).where(Factura.estado_dian == "aceptada")
        )
    ).scalar() or 0
    rechazadas = (
        await session.execute(
            select(func.count(Factura.id)).where(Factura.estado_dian == "rechazada")
        )
    ).scalar() or 0
    resoluciones_activas = (
        await session.execute(
            select(func.count(Resolucion.id)).where(Resolucion.activa == True)
        )
    ).scalar() or 0

    ultimas = (
        await session.execute(
            select(Factura)
            .order_by(desc(Factura.fecha_emision))
            .limit(10)
        )
    ).scalars().all()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "usuario": user,
            "environment": settings.dian_environment,
            "stats": {
                "total_facturas": total,
                "aceptadas": aceptadas,
                "rechazadas": rechazadas,
                "resoluciones_activas": resoluciones_activas,
                "certificado_configurado": bool(
                    settings.certificate_path
                    and Path(settings.certificate_path).exists()
                ),
            },
            "ultimas_facturas": ultimas,
        },
    )


# ── Resoluciones ─────────────────────────────────────────────────────────

@router.get("/resoluciones", response_class=HTMLResponse)
async def listar_resoluciones_web(
    request: Request, session: AsyncSession = Depends(get_session)
):
    user = _require_admin(request)
    result = await session.execute(
        select(Resolucion).order_by(desc(Resolucion.fecha_autorizacion))
    )
    resoluciones = result.scalars().all()
    return templates.TemplateResponse(
        "resoluciones.html",
        {
            "request": request,
            "usuario": user,
            "environment": settings.dian_environment,
            "resoluciones": [
                {
                    "id": str(r.id),
                    "prefijo": r.prefijo,
                    "tipo_documento": r.tipo_documento,
                    "rango": f"{r.rango_inicio} - {r.rango_fin}",
                    "consecutivo_actual": r.consecutivo_actual,
                    "activa": r.activa,
                    "vencida": r.vencida,
                    "agotado": r.agotado,
                    "fecha_vencimiento": r.fecha_vencimiento.isoformat()
                    if hasattr(r.fecha_vencimiento, "isoformat")
                    else str(r.fecha_vencimiento),
                }
                for r in resoluciones
            ],
        },
    )


class ResolucionCreate:
    prefijo: str
    tipo_documento: str
    rango_inicio: int
    rango_fin: int
    fecha_autorizacion: date
    fecha_vencimiento: date
    clave_tecnica: str


@router.post("/resoluciones/crear")
async def crear_resolucion_web(
    request: Request, session: AsyncSession = Depends(get_session)
):
    user = _require_admin(request)
    form = await request.form()

    try:
        r = Resolucion(
            id=uuid.uuid4(),
            prefijo=str(form.get("prefijo", "")).strip().upper(),
            tipo_documento=str(form.get("tipo_documento", "FEV")),
            rango_inicio=int(form.get("rango_inicio", 0)),
            rango_fin=int(form.get("rango_fin", 0)),
            consecutivo_actual=int(form.get("rango_inicio", 0)) - 1,
            fecha_autorizacion=date.fromisoformat(
                str(form.get("fecha_autorizacion", ""))
            ),
            fecha_vencimiento=date.fromisoformat(
                str(form.get("fecha_vencimiento", ""))
            ),
            clave_tecnica=str(form.get("clave_tecnica", "")).strip(),
        )
        session.add(r)
        await session.commit()
    except Exception as e:
        return templates.TemplateResponse(
            "resoluciones.html",
            {
                "request": request,
                "usuario": user,
                "environment": settings.dian_environment,
                "resoluciones": [],
                "_flash": [("error", f"Error al crear resolución: {e}")],
            },
        )

    resp = RedirectResponse("/admin/resoluciones", status_code=302)
    return resp


@router.post("/resoluciones/{resolucion_id}/desactivar")
async def desactivar_resolucion_web(
    resolucion_id: str, session: AsyncSession = Depends(get_session)
):
    from uuid import UUID
    result = await session.execute(
        select(Resolucion).where(Resolucion.id == UUID(resolucion_id))
    )
    r = result.scalar_one_or_none()
    if r:
        r.activa = False
        await session.commit()
    return RedirectResponse("/admin/resoluciones", status_code=302)


# ── Certificado ──────────────────────────────────────────────────────────

@router.get("/certificado", response_class=HTMLResponse)
async def certificado_page(request: Request):
    user = _require_admin(request)

    cert_info = None
    if settings.certificate_path and Path(settings.certificate_path).exists():
        cert_path = settings.certificate_path
        try:
            from app.dian.signer import get_certificate_info
            info = get_certificate_info(cert_path, settings.certificate_password)
            cert_info = {
                "path": cert_path,
                "size": Path(cert_path).stat().st_size,
                "info": info,
            }
        except Exception as e:
            cert_info = {"path": cert_path, "size": 0, "info": None, "error": str(e)}

    return templates.TemplateResponse(
        "certificado.html",
        {
            "request": request,
            "usuario": user,
            "environment": settings.dian_environment,
            "certificado": cert_info,
        },
    )


@router.post("/certificado/subir")
async def subir_certificado_web(
    request: Request,
    certificado: UploadFile = File(...),
    password: str = Form(""),
):
    user = _require_admin(request)

    cert_dir = BASE_DIR / "certs"
    cert_dir.mkdir(exist_ok=True)

    dest = cert_dir / certificado.filename
    content = await certificado.read()
    with open(dest, "wb") as f:
        f.write(content)

    # Update .env file with new paths
    _update_env(
        certificate_path=str(dest),
        certificate_password=password or settings.certificate_password,
    )

    # Reload settings
    settings.certificate_path = str(dest)
    if password:
        settings.certificate_password = password

    resp = RedirectResponse("/admin/certificado", status_code=302)
    return resp


# ── Configuración ────────────────────────────────────────────────────────

@router.get("/configuracion", response_class=HTMLResponse)
async def configuracion_page(request: Request):
    user = _require_admin(request)
    return templates.TemplateResponse(
        "configuracion.html",
        {
            "request": request,
            "usuario": user,
            "environment": settings.dian_environment,
            "config": {
                "emisor_nit": settings.emisor_nit,
                "emisor_razon_social": settings.emisor_razon_social,
                "emisor_nombre_comercial": settings.emisor_nombre_comercial,
                "emisor_direccion": settings.emisor_direccion,
                "emisor_municipio": settings.emisor_municipio,
                "emisor_departamento": settings.emisor_departamento,
                "emisor_telefono": settings.emisor_telefono,
                "emisor_email": settings.emisor_email,
                "regmen_fiscal": settings.regmen_fiscal,
                "dian_environment": settings.dian_environment,
            },
        },
    )


@router.post("/configuracion")
async def configuracion_save(request: Request):
    user = _require_admin(request)
    form = await request.form()

    updates = {}
    mapping = {
        "emisor_nit": "emisor_nit",
        "emisor_razon_social": "emisor_razon_social",
        "emisor_nombre_comercial": "emisor_nombre_comercial",
        "emisor_direccion": "emisor_direccion",
        "emisor_municipio": "emisor_municipio",
        "emisor_departamento": "emisor_departamento",
        "emisor_telefono": "emisor_telefono",
        "emisor_email": "emisor_email",
        "regmen_fiscal": "regmen_fiscal",
        "dian_environment": "dian_environment",
    }
    for field, attr in mapping.items():
        value = str(form.get(field, "")).strip()
        updates[attr] = value
        setattr(settings, attr, value)

    _update_env(**updates)

    resp = RedirectResponse("/admin/configuracion", status_code=302)
    return resp


# ── Facturas ─────────────────────────────────────────────────────────────

@router.get("/facturas", response_class=HTMLResponse)
async def facturas_web(
    request: Request,
    q: str = "",
    session: AsyncSession = Depends(get_session),
):
    user = _require_admin(request)

    query = select(Factura).order_by(desc(Factura.fecha_emision))
    if q:
        q_filter = f"%{q}%"
        query = query.where(
            Factura.adquiriente_razon_social.ilike(q_filter)
            | Factura.adquiriente_nit.ilike(q_filter)
        )

    result = await session.execute(query.limit(100))
    facturas = result.scalars().all()

    return templates.TemplateResponse(
        "facturas.html",
        {
            "request": request,
            "usuario": user,
            "environment": settings.dian_environment,
            "facturas": facturas,
            "query": q,
        },
    )


# ── Sync Logs ────────────────────────────────────────────────────────────

@router.get("/sync-logs", response_class=HTMLResponse)
async def sync_logs_web(
    request: Request, session: AsyncSession = Depends(get_session)
):
    user = _require_admin(request)
    result = await session.execute(
        select(SyncLog).order_by(desc(SyncLog.creado_en)).limit(100)
    )
    logs = result.scalars().all()

    return templates.TemplateResponse(
        "sync-logs.html",
        {
            "request": request,
            "usuario": user,
            "environment": settings.dian_environment,
            "logs": logs,
        },
    )


# ── Helpers ──────────────────────────────────────────────────────────────

ENV_PATH = BASE_DIR.parent / ".env"


def _update_env(**kwargs):
    """Update key=value pairs in .env file, preserving existing values."""
    if not ENV_PATH.exists():
        return

    lines = ENV_PATH.read_text().splitlines()
    updated = []
    seen_keys = set()

    for line in lines:
        line_stripped = line.strip()
        if "=" in line_stripped and not line_stripped.startswith("#"):
            key = line_stripped.split("=", 1)[0].strip()
            if key in kwargs:
                value = kwargs[key]
                if value:
                    updated.append(f"{key}={value}")
                else:
                    updated.append(line)
                seen_keys.add(key)
            else:
                updated.append(line)
        else:
            updated.append(line)

    # Add keys not found
    for key, value in kwargs.items():
        if key not in seen_keys and value:
            updated.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(updated) + "\n")
