from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.routes.auth import require_auth
from app.dian.client import transmitir_factura, consultar_estado_dian
from app.dian.contingency import get_contingency_manager
from app.services.factura_service import reconciliar_estados_pendientes
from app.models import Factura

router = APIRouter(prefix="/api/v1/dian", tags=["dian"], dependencies=[Depends(require_auth)])


@router.post("/transmitir/{documento_id}")
async def transmitir_a_dian(documento_id: str, session: AsyncSession = Depends(get_session)):
    from uuid import UUID
    result = await session.execute(select(Factura).where(Factura.id == UUID(documento_id)))
    factura = result.scalar_one_or_none()
    if not factura:
        raise HTTPException(status_code=404, detail="Documento no encontrado")

    if not factura.xml_enviado:
        raise HTTPException(status_code=400, detail="No hay XML firmado disponible")

    dian_response = transmitir_factura(factura.xml_enviado.encode("utf-8"))
    factura.xml_recibido = dian_response.get("raw_response")
    if dian_response["status"] == "aceptada":
        factura.estado_dian = "aceptada"
        if dian_response.get("cufe"):
            factura.cufe = dian_response["cufe"]
    elif dian_response["status"] == "rechazada":
        factura.estado_dian = "rechazada"
        factura.mensaje_dian = dian_response.get("error_message")
    await session.commit()

    return {"documento_id": documento_id, **dian_response}


@router.get("/proveedor/estado")
async def estado_proveedor():
    """Chequeo de conexión con el PT (solo lectura, no emite)."""
    from config import settings
    from app.fe import get_proveedor
    if not settings.fe_provider or settings.fe_provider.lower() == "directo":
        return {"ok": False, "proveedor": "directo",
                "mensaje": "FE_PROVIDER=directo: no usa proveedor externo"}
    try:
        prov = get_proveedor()
    except NotImplementedError as e:
        return {"ok": False, "proveedor": settings.fe_provider, "mensaje": str(e)}
    return {"proveedor": prov.nombre, **(await prov.verificar_conexion())}


@router.post("/reconciliar")
async def reconciliar_pendientes(session: AsyncSession = Depends(get_session)):
    """Consulta al PT el estado de las facturas en proceso (respaldo del webhook)."""
    return await reconciliar_estados_pendientes(session)


@router.post("/contingencia/iniciar")
async def iniciar_contingencia():
    cm = get_contingency_manager()
    cm.start_contingency()
    return {"status": "contingencia_iniciada"}


@router.post("/contingencia/finalizar")
async def finalizar_contingencia():
    cm = get_contingency_manager()
    pending = cm.end_contingency()
    return {"status": "contingencia_finalizada", "pendientes": len(pending)}


@router.get("/contingencia/estado")
async def estado_contingencia():
    cm = get_contingency_manager()
    return {"activa": cm.is_active, "pendientes": cm.get_pending_count()}
