import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.routes.auth import require_auth
from app.models import Resolucion

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(require_auth)])


class ResolucionCreate(BaseModel):
    prefijo: str
    tipo_documento: str
    rango_inicio: int
    rango_fin: int
    fecha_autorizacion: date
    fecha_vencimiento: date
    clave_tecnica: str


class ResolucionUpdate(BaseModel):
    activa: bool | None = None
    fecha_vencimiento: date | None = None
    rango_fin: int | None = None
    clave_tecnica: str | None = None


@router.post("/resoluciones")
async def crear_resolucion(req: ResolucionCreate, session: AsyncSession = Depends(get_session)):
    resolucion = Resolucion(
        id=uuid.uuid4(),
        prefijo=req.prefijo.upper(),
        tipo_documento=req.tipo_documento,
        rango_inicio=req.rango_inicio,
        rango_fin=req.rango_fin,
        consecutivo_actual=req.rango_inicio - 1,
        fecha_autorizacion=req.fecha_autorizacion,
        fecha_vencimiento=req.fecha_vencimiento,
        clave_tecnica=req.clave_tecnica,
    )
    session.add(resolucion)
    await session.commit()
    return {"id": str(resolucion.id), "prefijo": resolucion.prefijo}


@router.get("/resoluciones")
async def listar_resoluciones(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Resolucion).order_by(Resolucion.fecha_autorizacion.desc())
    )
    resoluciones = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "prefijo": r.prefijo,
            "tipo_documento": r.tipo_documento,
            "rango": f"{r.rango_inicio}-{r.rango_fin}",
            "consecutivo_actual": r.consecutivo_actual,
            "activa": r.activa,
            "vencida": r.vencida,
            "agotado": r.agotado,
            "fecha_autorizacion": r.fecha_autorizacion.isoformat(),
            "fecha_vencimiento": r.fecha_vencimiento.isoformat(),
        }
        for r in resoluciones
    ]


@router.put("/resoluciones/{resolucion_id}")
async def actualizar_resolucion(resolucion_id: str, req: ResolucionUpdate,
                                 session: AsyncSession = Depends(get_session)):
    from uuid import UUID
    result = await session.execute(select(Resolucion).where(Resolucion.id == UUID(resolucion_id)))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(status_code=404, detail="Resolucion not found")
    if req.activa is not None:
        r.activa = req.activa
    if req.fecha_vencimiento:
        r.fecha_vencimiento = req.fecha_vencimiento
    if req.rango_fin:
        r.rango_fin = req.rango_fin
    if req.clave_tecnica:
        r.clave_tecnica = req.clave_tecnica
    await session.commit()
    return {"status": "actualizada"}


@router.post("/certificado")
async def subir_certificado(file: UploadFile = File(...)):
    import os
    from pathlib import Path
    from config import BASE_DIR

    cert_dir = BASE_DIR / "certs"
    cert_dir.mkdir(exist_ok=True)
    dest = cert_dir / file.filename
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    return {"status": "ok", "path": str(dest), "size": len(content)}


@router.get("/certificado")
async def estado_certificado():
    from config import settings
    from pathlib import Path

    cert_path = settings.certificate_path
    if not cert_path or not Path(cert_path).exists():
        return {"status": "no_certificate"}

    from app.dian.signer import get_certificate_info
    info = get_certificate_info(cert_path, settings.certificate_password)
    return {"status": "ok", "info": info}


@router.get("/dashboard")
async def dashboard(session: AsyncSession = Depends(get_session)):
    from sqlalchemy import func
    from app.models import Factura

    total = (await session.execute(select(func.count(Factura.id)))).scalar() or 0
    aceptadas = (await session.execute(
        select(func.count(Factura.id)).where(Factura.estado_dian == "aceptada")
    )).scalar() or 0
    rechazadas = (await session.execute(
        select(func.count(Factura.id)).where(Factura.estado_dian == "rechazada")
    )).scalar() or 0

    resoluciones = (await session.execute(
        select(Resolucion).where(Resolucion.activa == True)
    )).scalars().all()

    return {
        "total_facturas": total,
        "aceptadas": aceptadas,
        "rechazadas": rechazadas,
        "resoluciones_activas": len(resoluciones),
        "certificado_configurado": bool(settings.certificate_path),
    }
