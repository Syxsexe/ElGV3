"""
Webhooks entrantes de los Proveedores Tecnológicos (capa app/fe).

Aquí "recibimos la conexión" del PT: cuando DIAN termina de validar (asíncrono),
Matias envía un POST con el veredicto (`document.accepted` / `document.rejected`).
Verificamos la firma HMAC, normalizamos el evento y actualizamos la factura de
forma idempotente.

Este endpoint NO usa el auth del POS: la autenticidad se prueba con la firma HMAC
(`X-Webhook-Signature`) contra `MATIAS_WEBHOOK_SECRET`.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.fe import get_proveedor, EventoWebhook
from app.models import Factura

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/fe", tags=["webhooks"])

# Estados finales: no se degradan por eventos posteriores.
_FINALES = {"aceptada", "rechazada", "anulada"}


async def _buscar_factura(session: AsyncSession, evento: EventoWebhook) -> Factura | None:
    if evento.track_id:
        res = await session.execute(
            select(Factura).where(Factura.track_id == evento.track_id)
        )
        factura = res.scalar_one_or_none()
        if factura:
            return factura
    if evento.cufe:
        res = await session.execute(select(Factura).where(Factura.cufe == evento.cufe))
        factura = res.scalar_one_or_none()
        if factura:
            return factura
    return None


@router.post("/{proveedor}")
async def recibir_webhook(
    proveedor: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    body = await request.body()
    firma = request.headers.get("X-Webhook-Signature")

    try:
        prov = get_proveedor(proveedor)
    except NotImplementedError:
        raise HTTPException(status_code=404, detail=f"Proveedor '{proveedor}' desconocido")

    # 1. Verificar firma HMAC (fail-closed).
    if not prov.verificar_firma_webhook(body, firma):
        logger.warning("Webhook %s con firma inválida", proveedor)
        raise HTTPException(status_code=401, detail="Firma inválida")

    # 2. Parsear payload.
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload no es JSON válido")

    evento = prov.parse_webhook(payload)
    logger.info("Webhook %s: %s track=%s estado=%s",
                proveedor, evento.evento, evento.track_id, evento.estado)

    # 3. Ubicar la factura.
    factura = await _buscar_factura(session, evento)
    if factura is None:
        # Ack 200 para que el PT no reintente indefinidamente por un doc que no es nuestro.
        logger.warning("Webhook %s sin factura para track=%s cufe=%s",
                       proveedor, evento.track_id, evento.cufe)
        return {"status": "ignored", "reason": "documento no encontrado"}

    # 4. Actualizar idempotentemente.
    if factura.estado_dian in _FINALES and evento.estado not in _FINALES:
        # Ya estaba en estado final; un evento intermedio no lo degrada.
        return {"status": "noop", "estado": factura.estado_dian}

    if factura.estado_dian == evento.estado:
        return {"status": "noop", "estado": factura.estado_dian}

    factura.estado_dian = evento.estado
    if evento.mensaje:
        factura.mensaje_dian = evento.mensaje
    if evento.cufe and not factura.cufe:
        factura.cufe = evento.cufe
    if evento.estado in _FINALES:
        from datetime import datetime
        factura.fecha_validacion_dian = datetime.now()

    await session.commit()
    return {"status": "ok", "estado": factura.estado_dian, "numero": evento.numero}
