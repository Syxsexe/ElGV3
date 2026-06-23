"""
Factura Service — Orquesta el flujo completo de facturación electrónica DIAN.
"""

import uuid as uuid_lib
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from app.models import Factura, Resolucion, SyncLog
from app.dian.cufe import generar_cufe
from app.dian.qr import generar_qr_base64
from app.dian.xml_generator import generar_xml_factura
from app.dian.signer import firmar_xml
from app.dian.client import transmitir_factura, consultar_estado_dian
from app.dian.contingency import get_contingency_manager


def _round2(val) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"))


async def crear_y_transmitir_factura(
    session: AsyncSession,
    *,
    venta_id_local: int,
    uuid_operacion: str,
    adquiriente_nit: str,
    adquiriente_razon_social: str,
    adquiriente_email: str | None = None,
    adquiriente_direccion: str | None = None,
    adquiriente_telefono: str | None = None,
    items: list[dict],
    total: Decimal | float,
    descuento: Decimal | float = 0,
    notas: str | None = None,
) -> dict:
    """
    Full electronic invoice creation and DIAN transmission.
    1. Get active invoice resolution
    2. Calculate values
    3. Create DB record
    4. Generate CUFE
    5. Generate XML
    6. Sign XML
    7. Transmit to DIAN
    8. Update record with response
    """

    # 1. Get active resolution
    result = await session.execute(
        select(Resolucion).where(
            Resolucion.activa == True,
            Resolucion.tipo_documento == "FEV",
            Resolucion.agotado == False,
        ).order_by(Resolucion.fecha_autorizacion.desc()).limit(1)
    )
    resolucion = result.scalar_one_or_none()
    if not resolucion:
        return {
            "status": "error",
            "error": "No hay resolución activa disponible para facturación electrónica",
        }

    # 2. Calculate values
    total_dec = _round2(total)
    descuento_dec = _round2(descuento)
    total_con_descuento = _round2(total_dec - descuento_dec)
    iva_porcentaje = Decimal("19.00")
    total_base = _round2(total_con_descuento / (1 + iva_porcentaje / 100))
    iva = _round2(total_con_descuento - total_base)

    # 3. Next consecutive
    consecutivo = resolucion.consecutivo_actual + 1
    resolucion.consecutivo_actual = consecutivo

    fecha_ahora = datetime.now()

    # 4. Generate CUFE
    cufe = generar_cufe(
        numero_factura=f"{resolucion.prefijo}{consecutivo}",
        fecha_emision=fecha_ahora,
        nit_emisor=settings.emisor_nit,
        nit_adquiriente=adquiriente_nit,
        total_sin_impuestos=total_base,
        total_con_impuestos=total_con_descuento,
        clave_tecnica=resolucion.clave_tecnica,
        tipo_documento="01",
    )

    # 5. QR Code
    qr_b64 = generar_qr_base64(
        nit_emisor=settings.emisor_nit,
        numero_factura=f"{resolucion.prefijo}{consecutivo}",
        cufe=cufe,
        total=float(total_con_descuento),
        iva=float(iva),
        fecha=fecha_ahora.isoformat(),
    )

    # 6. Create DB record
    factura = Factura(
        id=uuid_lib.uuid4(),
        resolucion_id=resolucion.id,
        prefijo=resolucion.prefijo,
        consecutivo=consecutivo,
        fecha_emision=fecha_ahora,
        tipo_documento="FEV",
        adquiriente_nit=adquiriente_nit,
        adquiriente_razon_social=adquiriente_razon_social,
        adquiriente_email=adquiriente_email,
        adquiriente_direccion=adquiriente_direccion,
        adquiriente_telefono=adquiriente_telefono,
        total_base=total_base,
        iva=iva,
        iva_porcentaje=iva_porcentaje,
        total_impuestos=iva,
        total=total_con_descuento,
        cufe=cufe,
        qr_code=qr_b64,
        estado_dian="pendiente",
        items=items,
        venta_id_local=venta_id_local,
        notas=notas,
    )
    session.add(factura)

    # 7 . Check contingency
    cm = get_contingency_manager()
    if cm.is_active:
        factura.estado_dian = "contingencia"
        cm.add_pending({
            "factura_id": str(factura.id),
            "prefijo": factura.prefijo,
            "consecutivo": factura.consecutivo,
            "items": items,
        })
        await session.commit()
        return {
            "status": "contingencia",
            "cufe": cufe,
            "qr": qr_b64,
            "factura_id": str(factura.id),
            "numero": f"{factura.prefijo}{factura.consecutivo}",
            "mensaje": "Documento generado en contingencia. Se transmitirá cuando DIAN esté disponible.",
        }

    # 8. Generate XML
    try:
        xml_unsigned = generar_xml_factura(
            prefijo=resolucion.prefijo,
            consecutivo=consecutivo,
            fecha_emision=fecha_ahora,
            nit_emisor=settings.emisor_nit,
            razon_social_emisor=settings.emisor_razon_social,
            nit_adquiriente=adquiriente_nit,
            razon_social_adquiriente=adquiriente_razon_social,
            direccion_adquiriente=adquiriente_direccion,
            email_adquiriente=adquiriente_email,
            telefono_adquiriente=adquiriente_telefono,
            items=items,
            total_base=total_base,
            iva=iva,
            iva_porcentaje=iva_porcentaje,
            total=total_con_descuento,
            cufe=cufe,
            notas=notas,
        )
    except Exception as e:
        factura.estado_dian = "error"
        factura.mensaje_dian = f"Error generando XML: {e}"
        await session.commit()
        return {
            "status": "error",
            "error": f"Error generando XML: {e}",
        }

    # 9. Sign XML
    try:
        cert_path = settings.certificate_path
        cert_pass = settings.certificate_password
        if cert_path and cert_pass:
            xml_signed = firmar_xml(
                xml_unsigned, cert_path, cert_pass,
                reference_uri=f"#{resolucion.prefijo}{consecutivo}",
            )
        else:
            # Development mode — skip actual signing
            xml_signed = xml_unsigned
    except Exception as e:
        factura.estado_dian = "error"
        factura.mensaje_dian = f"Error firmando XML: {e}"
        await session.commit()
        return {
            "status": "error",
            "error": f"Error firmando XML: {e}",
        }

    factura.xml_enviado = xml_signed.decode("utf-8")

    # 10. Transmit to DIAN
    try:
        dian_response = transmitir_factura(xml_signed)
    except Exception as e:
        factura.estado_dian = "error"
        factura.mensaje_dian = f"Error transmitiendo a DIAN: {e}"
        await session.commit()
        return {
            "status": "error",
            "error": f"Error transmitiendo a DIAN: {e}",
        }

    # 11. Process DIAN response
    factura.xml_recibido = dian_response.get("raw_response")
    if dian_response["status"] == "aceptada":
        factura.estado_dian = "aceptada"
        factura.fecha_validacion_dian = datetime.now()
        if dian_response.get("cufe"):
            factura.cufe = dian_response["cufe"]
    elif dian_response["status"] == "rechazada":
        factura.estado_dian = "rechazada"
        factura.mensaje_dian = dian_response.get("error_message", "Rechazada por DIAN")
    else:
        factura.estado_dian = "error"
        factura.mensaje_dian = dian_response.get("error_message", "Error desconocido")

    await session.commit()

    return {
        "status": factura.estado_dian,
        "cufe": factura.cufe,
        "qr": qr_b64,
        "factura_id": str(factura.id),
        "numero": f"{factura.prefijo}{factura.consecutivo}",
        "mensaje_dian": factura.mensaje_dian,
    }
