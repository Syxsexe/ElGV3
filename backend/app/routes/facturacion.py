from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.routes.auth import require_auth
from app.services.factura_service import crear_y_transmitir_factura
from app.models import Factura, NotaCredito, NotaDebito

router = APIRouter(prefix="/api/v1/facturacion", tags=["facturacion"], dependencies=[Depends(require_auth)])


class FacturaRequest(BaseModel):
    venta_id_local: int
    uuid_operacion: str
    adquiriente_nit: str
    adquiriente_razon_social: str
    adquiriente_email: str | None = None
    adquiriente_direccion: str | None = None
    adquiriente_telefono: str | None = None
    items: list = []
    total: float = 0
    descuento: float = 0
    notas: str | None = None


@router.post("/factura")
async def crear_factura(req: FacturaRequest, session: AsyncSession = Depends(get_session)):
    result = await crear_y_transmitir_factura(
        session=session,
        venta_id_local=req.venta_id_local,
        uuid_operacion=req.uuid_operacion,
        adquiriente_nit=req.adquiriente_nit,
        adquiriente_razon_social=req.adquiriente_razon_social,
        adquiriente_email=req.adquiriente_email,
        adquiriente_direccion=req.adquiriente_direccion,
        adquiriente_telefono=req.adquiriente_telefono,
        items=req.items,
        total=req.total,
        descuento=req.descuento,
        notas=req.notas,
    )
    return result


@router.get("/factura/{factura_id}")
async def obtener_factura(factura_id: str, session: AsyncSession = Depends(get_session)):
    from uuid import UUID
    result = await session.execute(
        select(Factura).where(Factura.id == UUID(factura_id))
    )
    factura = result.scalar_one_or_none()
    if not factura:
        raise HTTPException(status_code=404, detail="Factura not found")
    return {
        "id": str(factura.id),
        "numero": f"{factura.prefijo}{factura.consecutivo}",
        "cufe": factura.cufe,
        "estado_dian": factura.estado_dian,
        "total": float(factura.total),
        "adquiriente": factura.adquiriente_razon_social,
        "fecha": factura.fecha_emision.isoformat() if factura.fecha_emision else None,
        "mensaje_dian": factura.mensaje_dian,
        "qr": factura.qr_code,
    }


@router.get("/estadisticas")
async def estadisticas_facturacion(session: AsyncSession = Depends(get_session)):
    total = await session.execute(select(func.count(Factura.id)))
    aceptadas = await session.execute(
        select(func.count(Factura.id)).where(Factura.estado_dian == "aceptada")
    )
    rechazadas = await session.execute(
        select(func.count(Factura.id)).where(Factura.estado_dian == "rechazada")
    )
    pendientes = await session.execute(
        select(func.count(Factura.id)).where(Factura.estado_dian == "pendiente")
    )
    contingencia = await session.execute(
        select(func.count(Factura.id)).where(Factura.estado_dian == "contingencia")
    )
    return {
        "total": total.scalar() or 0,
        "aceptadas": aceptadas.scalar() or 0,
        "rechazadas": rechazadas.scalar() or 0,
        "pendientes": pendientes.scalar() or 0,
        "contingencia": contingencia.scalar() or 0,
    }
