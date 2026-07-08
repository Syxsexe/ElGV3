"""
Mapeo de `DocumentoFE` (modelo interno) al JSON que espera Matias API en
`POST /invoice` (facturas/POS) y `POST /notes/credit|debit` (notas). El cuerpo
JSON es el mismo en todos; el tipo lo determina `type_document_id` + la ruta.

⚠️ Los IDs de catálogo (identity_document_id, city_id, tax_id, means_payment_id…)
son códigos propios de Matias/DIAN. Los valores por defecto de abajo replican los
ejemplos de la documentación y deben **verificarse contra el catálogo real** del
sandbox (endpoint de Tablas y Catálogos, auth no requerida) antes de producción.
Si el `AdquirienteFE`/`DocumentoFE` trae un ID explícito, ese gana sobre el default.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.fe.base import DocumentoFE, ItemFE, AdquirienteFE

# ── Defaults de catálogo (VERIFICAR contra catálogo Matias) ───────────────────
CURRENCY_COP = "272"
OP_ESTANDAR = 1                 # operation_type_id
UNIDAD_DEFAULT = "70"           # quantity_units_id (unidad genérica) — verificar
TAX_IVA = "1"                   # tax_id IVA
IDENT_CEDULA = "3"              # identity_document_id cédula ciudadanía — verificar
IDENT_NIT = "6"                 # identity_document_id NIT — verificar
ORG_NATURAL = 2                 # type_organization_id persona natural
ORG_JURIDICA = 1                # type_organization_id persona jurídica
REGIMEN_NO_RESP = 2             # tax_regime_id (No responsable de IVA) — verificar
RESP_R99 = "5"                  # tax_level_id (R-99-PN sin responsabilidad) — verificar
PAIS_CO = "45"                  # country_id Colombia — verificar
CIUDAD_DEFAULT = "836"          # city_id (Bogotá) — verificar / configurar por emisor
METODO_CONTADO = 1              # payment_method_id contado
MEDIO_EFECTIVO = 10             # means_payment_id efectivo

# type_document_id según tipo interno.
TIPO_DOC_ID = {
    "factura": 7,
    "nota_credito": 5,
    "nota_debito": 4,
}

# NIT genérico de consumidor final (DIAN).
NIT_CONSUMIDOR_FINAL = "222222222222"


def _money(val: Decimal | float | int) -> str:
    """Formatea un monto a string con 2 decimales (formato de montos de Matias)."""
    return str(Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _num(val: Decimal | float | int) -> float:
    return float(Decimal(str(val)))


def _es_consumidor_final(adq: AdquirienteFE) -> bool:
    return not adq.nit or adq.nit.replace("-", "").strip() in ("", NIT_CONSUMIDOR_FINAL)


def _customer(adq: AdquirienteFE) -> dict[str, Any]:
    consumidor_final = _es_consumidor_final(adq)
    dni = NIT_CONSUMIDOR_FINAL if consumidor_final else adq.nit.replace("-", "").split("-")[0]

    # Persona natural por defecto; jurídica si trae NIT y tipo jurídico explícito.
    org = adq.tipo_organizacion_id or (ORG_NATURAL if consumidor_final else ORG_JURIDICA)
    ident = adq.tipo_documento_id or (IDENT_CEDULA if consumidor_final else IDENT_NIT)

    return {
        "company_name": adq.razon_social or "CONSUMIDOR FINAL",
        "dni": dni,
        "email": adq.email or "",
        "identity_document_id": ident,
        "type_organization_id": org,
        "tax_regime_id": adq.regimen_id or REGIMEN_NO_RESP,
        "tax_level_id": adq.responsabilidad_id or RESP_R99,
        "country_id": adq.pais_id or PAIS_CO,
        "city_id": adq.municipio_id or CIUDAD_DEFAULT,
        "address": adq.direccion or "",
        "postal_code": adq.codigo_postal or "",
    }


def _tax_total(base: Decimal, valor: Decimal, porcentaje: Decimal) -> dict[str, Any]:
    return {
        "tax_id": TAX_IVA,
        "tax_amount": _num(valor),
        "taxable_amount": _num(base),
        "percent": _num(porcentaje),
    }


def _line(item: ItemFE) -> dict[str, Any]:
    linea: dict[str, Any] = {
        "invoiced_quantity": str(_num(item.cantidad)),
        "quantity_units_id": item.unidad_id or UNIDAD_DEFAULT,
        "line_extension_amount": _money(item.subtotal),
        "description": item.descripcion,
        "code": item.codigo or "N/A",
        "price_amount": _money(item.precio_unit),
    }
    # Solo agrega tax_totals si la línea tiene IVA (>0).
    if Decimal(str(item.iva_valor)) > 0 or Decimal(str(item.iva_porcentaje)) > 0:
        linea["tax_totals"] = [
            _tax_total(item.subtotal, item.iva_valor, item.iva_porcentaje)
        ]
    return linea


def construir_payload(doc: DocumentoFE, *, generar_pdf: bool, enviar_email: bool) -> dict[str, Any]:
    """Construye el cuerpo JSON de `POST /documents` desde un `DocumentoFE`."""
    total_con_impuestos = Decimal(str(doc.total))
    base = Decimal(str(doc.total_base))

    payload: dict[str, Any] = {
        "resolution_number": doc.resolucion_numero,
        "prefix": doc.prefijo,
        "document_number": str(doc.consecutivo),
        "operation_type_id": OP_ESTANDAR,
        "type_document_id": TIPO_DOC_ID[doc.tipo],
        "date": doc.fecha_emision.strftime("%Y-%m-%d"),
        "time": doc.fecha_emision.strftime("%H:%M:%S"),
        "currency_id": CURRENCY_COP,
        "customer": _customer(doc.adquiriente),
        "payments": [
            {
                "payment_method_id": doc.metodo_pago_id or METODO_CONTADO,
                "means_payment_id": doc.medio_pago_id or MEDIO_EFECTIVO,
                "value_paid": _money(total_con_impuestos),
                "payment_due_date": doc.fecha_vencimiento
                or doc.fecha_emision.strftime("%Y-%m-%d"),
            }
        ],
        "legal_monetary_totals": {
            "line_extension_amount": _money(base),
            "tax_exclusive_amount": _money(base),
            "tax_inclusive_amount": _money(total_con_impuestos),
            "payable_amount": _money(total_con_impuestos),
        },
        "lines": [_line(it) for it in doc.items],
        "tax_totals": [_tax_total(base, Decimal(str(doc.iva)), doc.iva_porcentaje)]
        if Decimal(str(doc.iva)) > 0
        else [],
        "graphic_representation": 1 if generar_pdf else 0,
        "send_email": 1 if enviar_email else 0,
    }

    if doc.notas:
        payload["notes"] = doc.notas

    # Notas crédito/débito: referencia al documento afectado.
    # ⚠️ Estructura exacta de billing_reference por verificar con ejemplos Matias.
    if doc.tipo in ("nota_credito", "nota_debito") and (doc.cufe_referencia or doc.numero_referencia):
        payload["billing_reference"] = {
            "number": doc.numero_referencia,
            "uuid": doc.cufe_referencia,
            "issue_date": doc.fecha_emision.strftime("%Y-%m-%d"),
        }
        if doc.motivo:
            payload["discrepancy_response"] = {"description": doc.motivo}

    return payload
