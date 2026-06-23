"""
Sync Service — Procesa operaciones entrantes desde el POS desktop.
"""

import uuid as uuid_lib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SyncLog, Factura
from app.services.factura_service import crear_y_transmitir_factura


async def procesar_sync_venta(
    session: AsyncSession,
    payload: dict,
) -> dict:
    """
    Processes an incoming sale sync from the desktop POS.
    1. Validates and creates SyncLog
    2. Creates Factura and sends to DIAN
    3. Returns result to desktop
    """
    uuid_op = payload.get("uuid_operacion", str(uuid_lib.uuid4()))
    venta_id_local = payload.get("venta_id", 0)

    # Check for duplicates (idempotency)
    existing = await session.execute(
        select(SyncLog).where(SyncLog.uuid_operacion == uuid_op)
    )
    if existing.scalar_one_or_none():
        return {"status": "duplicado", "uuid": uuid_op}

    # Create sync log
    sync_log = SyncLog(
        id=uuid_lib.uuid4(),
        uuid_operacion=uuid_op,
        entidad_tipo="venta",
        entidad_id_local=venta_id_local,
        accion="crear",
        estado="pendiente",
        payload=payload,
    )
    session.add(sync_log)

    # Extract data for invoicing
    adquiriente = payload.get("adquiriente", {})
    items = payload.get("items", [])
    total = payload.get("total", 0)
    descuento = payload.get("descuento", 0)
    notas = payload.get("notas", "")

    # Determine if DEE POS or full invoice
    emitir_factura = bool(adquiriente.get("nit") and
                          adquiriente.get("nit") not in ("", "222222222222", "CONSUMIDOR_FINAL"))

    if emitir_factura:
        result = await crear_y_transmitir_factura(
            session=session,
            venta_id_local=venta_id_local,
            uuid_operacion=uuid_op,
            adquiriente_nit=adquiriente.get("nit", "222222222222"),
            adquiriente_razon_social=adquiriente.get("razon_social", "CONSUMIDOR FINAL"),
            adquiriente_email=adquiriente.get("email"),
            adquiriente_direccion=adquiriente.get("direccion"),
            adquiriente_telefono=adquiriente.get("telefono"),
            items=items,
            total=total,
            descuento=descuento,
            notas=notas,
        )
    else:
        # DEE POS — for now just mark as synced (full DEE POS in block 4)
        result = {
            "status": "dee_pos",
            "mensaje": "DEE POS registrado (transmisión pendiente)",
            "tipo": "DEE_POS",
        }

    # Update sync log
    sync_log.estado = "sincronizado" if result.get("status") in ("aceptada", "contingencia", "dee_pos") else "error"
    sync_log.resultado = result
    sync_log.sincronizado_en = datetime.now()
    if result.get("status") == "error":
        sync_log.error = result.get("error", "Unknown error")

    await session.commit()
    return {"uuid": uuid_op, **result}
