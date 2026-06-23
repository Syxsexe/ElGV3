from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.routes.auth import require_auth
from app.services.sync_service import procesar_sync_venta
from app.models import SyncLog

router = APIRouter(prefix="/api/v1/sync", tags=["sync"], dependencies=[Depends(require_auth)])


class VentoSyncRequest(BaseModel):
    uuid_operacion: str
    venta_id: int
    total: float = 0
    descuento: float = 0
    metodo_pago: str = "efectivo"
    tipo: str = "tienda"
    usuario_id: int | None = None
    sesion_id: int | None = None
    cliente_id: int | None = None
    notas: str | None = None
    adquiriente: dict | None = None
    items: list = []
    pagos: list = []


@router.post("/venta")
async def sync_venta(req: VentoSyncRequest, session: AsyncSession = Depends(get_session)):
    """Receives a sale from the desktop POS and starts DIAN processing."""
    result = await procesar_sync_venta(session, req.model_dump())
    return result


class CierreCajaRequest(BaseModel):
    uuid_operacion: str
    sesion_id: int
    monto_base: float = 0
    monto_base_digital: float = 0
    total_ventas: float = 0
    total_efectivo: float = 0
    total_digital: float = 0
    denominaciones: dict | None = None
    ventas: list = []
    notas: str | None = None


@router.post("/caja/cierre")
async def sync_cierre_caja(req: CierreCajaRequest, session: AsyncSession = Depends(get_session)):
    """Receives cash session closure — triggers DEE POS batch transmission."""
    sync_log = SyncLog(
        uuid_operacion=req.uuid_operacion,
        entidad_tipo="caja",
        entidad_id_local=req.sesion_id,
        accion="cerrar",
        payload=req.model_dump(),
    )
    session.add(sync_log)
    await session.commit()

    return {
        "uuid": req.uuid_operacion,
        "status": "recibido",
        "mensaje": "Cierre de caja recibido. DEE POS pendiente de transmisión.",
    }


@router.get("/estado/{uuid_operacion}")
async def estado_sincronizacion(uuid_operacion: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(SyncLog).where(SyncLog.uuid_operacion == uuid_operacion)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Operation not found")
    return {
        "uuid": log.uuid_operacion,
        "estado": log.estado,
        "entidad_tipo": log.entidad_tipo,
        "resultado": log.resultado,
        "error": log.error,
    }


@router.get("/pendientes")
async def operaciones_pendientes(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(SyncLog).where(SyncLog.estado == "pendiente").order_by(SyncLog.creado_en).limit(50)
    )
    logs = result.scalars().all()
    return [
        {
            "uuid": log.uuid_operacion,
            "entidad_tipo": log.entidad_tipo,
            "entidad_id_local": log.entidad_id_local,
            "accion": log.accion,
        }
        for log in logs
    ]
