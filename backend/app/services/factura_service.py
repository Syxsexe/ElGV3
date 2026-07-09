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
from app.models import Factura, Resolucion, SyncLog, NotaCredito, NotaDebito
from app.dian.cufe import generar_cufe
from app.dian.qr import generar_qr_base64
from app.dian.xml_generator import generar_xml_factura
from app.dian.signer import firmar_xml
from app.dian.client import transmitir_factura, consultar_estado_dian
from app.dian.contingency import get_contingency_manager
from app.fe import get_proveedor, DocumentoFE, ItemFE, AdquirienteFE


# Adquiriente genérico DIAN cuando la venta no se factura a un cliente concreto.
NIT_CONSUMIDOR_FINAL = "222222222222"
RAZON_CONSUMIDOR_FINAL = "CONSUMIDOR FINAL"


def _round2(val) -> Decimal:
    return Decimal(str(val)).quantize(Decimal("0.01"))


def _resolver_adquiriente(nit: str | None, razon_social: str | None) -> tuple[str, str]:
    """Aplica el consumidor final por defecto.

    Si no se indica un NIT concreto (o es el genérico), la factura va a
    'CONSUMIDOR FINAL' salvo que se pase explícitamente cliente + NIT.
    """
    nit_limpio = (nit or "").replace("-", "").strip()
    if not nit_limpio or nit_limpio == NIT_CONSUMIDOR_FINAL:
        return NIT_CONSUMIDOR_FINAL, (razon_social or RAZON_CONSUMIDOR_FINAL)
    return nit_limpio, (razon_social or RAZON_CONSUMIDOR_FINAL)


def _usar_proveedor_externo() -> bool:
    """True cuando FE_PROVIDER delega en un PT (capa app/fe), no en el flujo directo."""
    return bool(settings.fe_provider) and settings.fe_provider.lower() != "directo"


async def crear_y_transmitir_factura(
    session: AsyncSession,
    *,
    venta_id_local: int,
    uuid_operacion: str,
    adquiriente_nit: str | None = None,
    adquiriente_razon_social: str | None = None,
    adquiriente_email: str | None = None,
    adquiriente_direccion: str | None = None,
    adquiriente_telefono: str | None = None,
    items: list[dict],
    total: Decimal | float,
    descuento: Decimal | float = 0,
    notas: str | None = None,
    emitir_dian: bool = True,
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

    # 0. Adquiriente: consumidor final por defecto salvo que se indique cliente.
    adquiriente_nit, adquiriente_razon_social = _resolver_adquiriente(
        adquiriente_nit, adquiriente_razon_social
    )

    # 1. Calculate values (no dependen de la resolución).
    total_dec = _round2(total)
    descuento_dec = _round2(descuento)
    total_con_descuento = _round2(total_dec - descuento_dec)
    iva_porcentaje = Decimal("19.00")
    total_base = _round2(total_con_descuento / (1 + iva_porcentaje / 100))
    iva = _round2(total_con_descuento - total_base)

    # 2. Factura "solo local": no se emite a DIAN, numeración propia (prefijo LOC).
    if not emitir_dian:
        return await _guardar_factura_local(
            session,
            adquiriente_nit=adquiriente_nit,
            adquiriente_razon_social=adquiriente_razon_social,
            adquiriente_email=adquiriente_email,
            adquiriente_direccion=adquiriente_direccion,
            adquiriente_telefono=adquiriente_telefono,
            items=items,
            total_base=total_base,
            iva=iva,
            iva_porcentaje=iva_porcentaje,
            total_con_descuento=total_con_descuento,
            venta_id_local=venta_id_local,
            notas=notas,
        )

    # 3. Get active resolution (sólo para las que sí se emiten a DIAN).
    result = await session.execute(
        select(Resolucion).where(
            Resolucion.activa == True,
            Resolucion.tipo_documento == "FEV",
            # `agotado` es una @property, no una columna: usar la expresión real.
            Resolucion.consecutivo_actual < Resolucion.rango_fin,
        ).order_by(Resolucion.fecha_autorizacion.desc()).limit(1)
    )
    resolucion = result.scalar_one_or_none()
    if not resolucion:
        return {
            "status": "error",
            "error": "No hay resolución activa disponible para facturación electrónica",
        }

    # 4. Next consecutive
    consecutivo = resolucion.consecutivo_actual + 1
    resolucion.consecutivo_actual = consecutivo

    fecha_ahora = datetime.now()

    # 3b. Vía Proveedor Tecnológico (Matias…): delega XML/CUFE/firma/transmisión.
    if _usar_proveedor_externo():
        return await _emitir_via_proveedor(
            session,
            resolucion=resolucion,
            consecutivo=consecutivo,
            fecha_ahora=fecha_ahora,
            adquiriente_nit=adquiriente_nit,
            adquiriente_razon_social=adquiriente_razon_social,
            adquiriente_email=adquiriente_email,
            adquiriente_direccion=adquiriente_direccion,
            adquiriente_telefono=adquiriente_telefono,
            items=items,
            total_base=total_base,
            iva=iva,
            iva_porcentaje=iva_porcentaje,
            total_con_descuento=total_con_descuento,
            venta_id_local=venta_id_local,
            notas=notas,
        )

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


# ── Factura solo local (no emitida a DIAN) ───────────────────────────────────

async def _guardar_factura_local(
    session: AsyncSession,
    *,
    adquiriente_nit: str,
    adquiriente_razon_social: str,
    adquiriente_email: str | None,
    adquiriente_direccion: str | None,
    adquiriente_telefono: str | None,
    items: list[dict],
    total_base: Decimal,
    iva: Decimal,
    iva_porcentaje: Decimal,
    total_con_descuento: Decimal,
    venta_id_local: int,
    notas: str | None,
) -> dict:
    """Guarda una factura que NO se emite a DIAN, con numeración propia.

    Usa el prefijo `FACTURA_LOCAL_PREFIJO` (p.ej. LOC) y un consecutivo
    independiente del de la resolución electrónica, para no dejar huecos en la
    secuencia oficial. No genera CUFE ni consume resolución.
    """
    prefijo = (settings.factura_local_prefijo or "LOC")[:4]

    # Siguiente consecutivo local (max+1 dentro del mismo prefijo local).
    result = await session.execute(
        select(func.max(Factura.consecutivo)).where(Factura.prefijo == prefijo)
    )
    consecutivo = (result.scalar() or 0) + 1

    factura = Factura(
        id=uuid_lib.uuid4(),
        resolucion_id=None,
        prefijo=prefijo,
        consecutivo=consecutivo,
        fecha_emision=datetime.now(),
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
        estado_dian="local",
        items=items,
        venta_id_local=venta_id_local,
        notas=notas,
    )
    session.add(factura)
    await session.commit()

    return {
        "status": "local",
        "factura_id": str(factura.id),
        "numero": f"{prefijo}{consecutivo}",
        "mensaje": "Factura guardada solo en local (no emitida a DIAN).",
    }


# ── Vía Proveedor Tecnológico (capa app/fe) ──────────────────────────────────

def _items_a_itemsfe(items: list[dict], iva_porcentaje: Decimal) -> list[ItemFE]:
    """Convierte los items del POS (subtotal CON IVA) a `ItemFE` (base SIN IVA).

    Convención POS: `subtotal` de cada línea incluye IVA. Matias espera la base
    imponible, así que extraemos el IVA de cada línea.
    """
    factor = 1 + iva_porcentaje / 100
    itemsfe: list[ItemFE] = []
    for it in items:
        cant = Decimal(str(it.get("cantidad", 1)))
        subt_bruto = Decimal(str(it.get("subtotal", 0)))
        if subt_bruto <= 0:
            pu = Decimal(str(it.get("precio_unit", 0)))
            subt_bruto = _round2(cant * pu)
        base_linea = _round2(subt_bruto / factor)
        iva_linea = _round2(subt_bruto - base_linea)
        pu_base = _round2(base_linea / cant) if cant else base_linea
        itemsfe.append(ItemFE(
            descripcion=str(it.get("nombre") or it.get("descripcion") or "Producto"),
            cantidad=cant,
            precio_unit=pu_base,
            subtotal=base_linea,
            iva_porcentaje=iva_porcentaje if iva_linea > 0 else Decimal("0"),
            iva_valor=iva_linea,
            codigo=it.get("codigo") or it.get("codigo_producto"),
        ))
    return itemsfe


async def _emitir_via_proveedor(
    session: AsyncSession,
    *,
    resolucion: Resolucion,
    consecutivo: int,
    fecha_ahora: datetime,
    adquiriente_nit: str,
    adquiriente_razon_social: str,
    adquiriente_email: str | None,
    adquiriente_direccion: str | None,
    adquiriente_telefono: str | None,
    items: list[dict],
    total_base: Decimal,
    iva: Decimal,
    iva_porcentaje: Decimal,
    total_con_descuento: Decimal,
    venta_id_local: int,
    notas: str | None,
) -> dict:
    """Registra la factura y la emite a través del PT configurado (FE_PROVIDER)."""
    proveedor = get_proveedor()

    # Registro local en estado 'pendiente' (aún sin CUFE/track_id).
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
        estado_dian="pendiente",
        items=items,
        venta_id_local=venta_id_local,
        notas=notas,
        proveedor=proveedor.nombre,
    )
    session.add(factura)

    doc = DocumentoFE(
        tipo="factura",
        prefijo=resolucion.prefijo,
        consecutivo=consecutivo,
        resolucion_numero=resolucion.numero_resolucion or "",
        fecha_emision=fecha_ahora,
        adquiriente=AdquirienteFE(
            nit=adquiriente_nit,
            razon_social=adquiriente_razon_social,
            email=adquiriente_email,
            direccion=adquiriente_direccion,
            telefono=adquiriente_telefono,
        ),
        items=_items_a_itemsfe(items, iva_porcentaje),
        total_base=total_base,
        iva=iva,
        total=total_con_descuento,
        iva_porcentaje=iva_porcentaje,
        notas=notas,
    )

    resultado = await proveedor.emitir(doc)

    # Volcar resultado normalizado a la factura.
    factura.estado_dian = resultado.estado
    factura.track_id = resultado.track_id
    factura.cufe = resultado.cufe
    factura.qr_code = resultado.qr
    factura.pdf_url = resultado.pdf_url
    factura.xml_url = resultado.xml_url
    factura.mensaje_dian = resultado.mensaje
    if resultado.estado in ("aceptada", "rechazada"):
        factura.fecha_validacion_dian = datetime.now()

    await session.commit()

    return {
        "status": factura.estado_dian,
        "cufe": factura.cufe,
        "qr": factura.qr_code,
        "pdf_url": factura.pdf_url,
        "track_id": factura.track_id,
        "factura_id": str(factura.id),
        "numero": f"{factura.prefijo}{factura.consecutivo}",
        "mensaje_dian": factura.mensaje_dian,
        "proveedor": factura.proveedor,
    }


_PENDIENTES = ["en_proceso", "enviada", "pendiente"]


async def _reconciliar_modelo(session, proveedor, modelo, *, campo_id: str,
                              tiene_fecha_valida: bool, limite: int) -> tuple[int, list[dict]]:
    """Consulta al PT el estado de los documentos pendientes de un modelo y los
    actualiza. `campo_id` = atributo del identificador DIAN (cufe/cude)."""
    result = await session.execute(
        select(modelo)
        .where(
            modelo.proveedor == proveedor.nombre,
            modelo.estado_dian.in_(_PENDIENTES),
        )
        .limit(limite)
    )
    docs = result.scalars().all()

    detalle: list[dict] = []
    cambiados = 0
    for doc in docs:
        res = await proveedor.consultar_estado(
            prefijo=doc.prefijo, consecutivo=doc.consecutivo, track_id=doc.track_id,
        )
        if res.estado != doc.estado_dian and res.estado != "error":
            doc.estado_dian = res.estado
            if res.cufe and not getattr(doc, campo_id):
                setattr(doc, campo_id, res.cufe)
            if res.mensaje:
                doc.mensaje_dian = res.mensaje
            if tiene_fecha_valida and res.estado in ("aceptada", "rechazada"):
                doc.fecha_validacion_dian = datetime.now()
            cambiados += 1
            detalle.append({
                "tipo": modelo.__name__,
                "numero": f"{doc.prefijo}{doc.consecutivo}",
                "estado": res.estado,
            })
    return cambiados, detalle


async def reconciliar_estados_pendientes(session: AsyncSession, *, limite: int = 50) -> dict:
    """Respaldo/alternativa al webhook: consulta al PT el estado de los documentos
    en 'en_proceso'/'enviada'/'pendiente' (facturas Y notas crédito/débito) y
    actualiza su estado con `consultar_estado()`. Job periódico imprescindible en
    despliegue local sin webhook (veredicto DIAN asíncrono).
    """
    if not _usar_proveedor_externo():
        return {"reconciliadas": 0, "detalle": [], "motivo": "FE_PROVIDER=directo"}

    proveedor = get_proveedor()
    detalle: list[dict] = []
    total = 0
    # (modelo, campo id DIAN, ¿tiene fecha_validacion_dian?)
    objetivos = [
        (Factura, "cufe", True),
        (NotaCredito, "cude", False),
        (NotaDebito, "cude", False),
    ]
    for modelo, campo_id, tiene_fecha in objetivos:
        n, det = await _reconciliar_modelo(
            session, proveedor, modelo,
            campo_id=campo_id, tiene_fecha_valida=tiene_fecha, limite=limite,
        )
        total += n
        detalle.extend(det)

    if total:
        await session.commit()
    return {"reconciliadas": total, "detalle": detalle}
