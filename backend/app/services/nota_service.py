"""
Nota Service — emite notas crédito/débito a través del Proveedor Tecnológico
(capa app/fe). Referencia la factura afectada (CUFE + número) para el
`billing_reference` que exige DIAN.

Sólo cubre el camino PT (FE_PROVIDER != directo). El camino 'directo' de notas
(XML UBL + firma) usa app.dian.xml_notas y no está cableado a un servicio aún.
"""

from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Factura, Resolucion, NotaCredito, NotaDebito
from app.fe import get_proveedor, DocumentoFE, ItemFE, AdquirienteFE
from app.services.factura_service import (
    _round2, _items_a_itemsfe, _usar_proveedor_externo,
)

# tipo interno de nota -> (modelo, tipo_documento de resolución, prefijo por defecto)
_CONFIG = {
    "nota_credito": (NotaCredito, "NC"),
    "nota_debito": (NotaDebito, "ND"),
}


async def crear_y_emitir_nota(
    session: AsyncSession,
    *,
    tipo: str,                       # 'nota_credito' | 'nota_debito'
    factura_id: str,
    motivo: str,
    total: Decimal | float,
    items: list[dict] | None = None,
    iva_porcentaje: Decimal | float = Decimal("19"),
    concepto_id: str | None = None,  # response_id DIAN (NC 1-6 / ND 1-4); None → default del mapper
) -> dict:
    """Emite una nota (crédito/débito) referida a `factura_id` vía el PT."""
    if tipo not in _CONFIG:
        return {"status": "error", "error": f"Tipo de nota inválido: {tipo}"}
    if not _usar_proveedor_externo():
        return {"status": "error",
                "error": "Emisión de notas por PT requiere FE_PROVIDER != directo"}

    Modelo, tipo_res = _CONFIG[tipo]
    iva_porcentaje = Decimal(str(iva_porcentaje))

    # 1. Factura afectada (para referencia + adquiriente).
    res = await session.execute(
        select(Factura).where(Factura.id == uuid_lib.UUID(str(factura_id)))
    )
    factura = res.scalar_one_or_none()
    if not factura:
        return {"status": "error", "error": "Factura afectada no encontrada"}
    if not factura.cufe:
        return {"status": "error",
                "error": "La factura afectada no tiene CUFE (no está aceptada aún)"}

    # 2. Resolución de la nota (NC/ND).
    res = await session.execute(
        select(Resolucion).where(
            Resolucion.activa == True,
            Resolucion.tipo_documento == tipo_res,
            Resolucion.consecutivo_actual < Resolucion.rango_fin,
        ).order_by(Resolucion.fecha_autorizacion.desc()).limit(1)
    )
    resolucion = res.scalar_one_or_none()
    if not resolucion:
        return {"status": "error",
                "error": f"No hay resolución activa para {tipo_res}"}

    # 3. Valores + consecutivo.
    total_dec = _round2(total)
    base = _round2(total_dec / (1 + iva_porcentaje / 100))
    iva = _round2(total_dec - base)
    consecutivo = resolucion.consecutivo_actual + 1
    resolucion.consecutivo_actual = consecutivo
    fecha_ahora = datetime.now()

    # 4. Ítems: los provistos (subtotal CON IVA) o una línea resumen.
    if items:
        itemsfe = _items_a_itemsfe(items, iva_porcentaje)
    else:
        itemsfe = [ItemFE(
            descripcion=f"{'Nota crédito' if tipo == 'nota_credito' else 'Nota débito'} - {motivo}"[:200],
            cantidad=Decimal("1"),
            precio_unit=base,
            subtotal=base,
            iva_porcentaje=iva_porcentaje if iva > 0 else Decimal("0"),
            iva_valor=iva,
        )]

    # 5. Registro local en 'pendiente'.
    proveedor = get_proveedor()
    nota = Modelo(
        id=uuid_lib.uuid4(),
        factura_id=factura.id,
        resolucion_id=resolucion.id,
        prefijo=resolucion.prefijo,
        consecutivo=consecutivo,
        fecha_emision=fecha_ahora,
        motivo=motivo,
        total_base=base,
        iva=iva,
        total=total_dec,
        estado_dian="pendiente",
        proveedor=proveedor.nombre,
    )
    session.add(nota)

    # 6. Documento normalizado + emisión.
    doc = DocumentoFE(
        tipo=tipo,
        prefijo=resolucion.prefijo,
        consecutivo=consecutivo,
        resolucion_numero=resolucion.numero_resolucion or "",
        fecha_emision=fecha_ahora,
        adquiriente=AdquirienteFE(
            nit=factura.adquiriente_nit,
            razon_social=factura.adquiriente_razon_social,
            email=factura.adquiriente_email,
            direccion=factura.adquiriente_direccion,
            telefono=factura.adquiriente_telefono,
        ),
        items=itemsfe,
        total_base=base,
        iva=iva,
        total=total_dec,
        iva_porcentaje=iva_porcentaje,
        notas=motivo,
        cufe_referencia=factura.cufe,
        numero_referencia=f"{factura.prefijo}{factura.consecutivo}",
        fecha_referencia=factura.fecha_emision.strftime("%Y-%m-%d"),
        concepto_nota_id=concepto_id,
        motivo=motivo,
    )

    resultado = await proveedor.emitir(doc)

    # 7. Volcar resultado (las notas usan CUDE en lugar de CUFE).
    nota.estado_dian = resultado.estado
    nota.track_id = resultado.track_id
    nota.cude = resultado.cufe
    nota.qr_code = resultado.qr
    nota.pdf_url = resultado.pdf_url
    nota.xml_url = resultado.xml_url
    nota.mensaje_dian = resultado.mensaje

    await session.commit()

    return {
        "status": nota.estado_dian,
        "cude": nota.cude,
        "track_id": nota.track_id,
        "pdf_url": nota.pdf_url,
        "qr": nota.qr_code,
        "nota_id": str(nota.id),
        "numero": f"{nota.prefijo}{nota.consecutivo}",
        "mensaje_dian": nota.mensaje_dian,
        "proveedor": nota.proveedor,
    }
