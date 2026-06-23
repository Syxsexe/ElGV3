"""
DIAN CUFE/CUDE Generator
Código Único de Factura Electrónica / Documento Electrónico
Algorithm: SHA-384 of concatenated invoice fields
"""

import hashlib
from datetime import datetime
from decimal import Decimal


def _digits(val: Decimal | float | int | str) -> str:
    """Convert a numeric value to a string of digits (no decimals, no separators)."""
    if isinstance(val, str):
        val = Decimal(val)
    return f"{int(round(Decimal(str(val)), 0))}"


def _fmt_dian_date(dt: datetime | str) -> str:
    """Format datetime as DIAN expects: YYYY-MM-DDTHH:mm:ss"""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _clean_nit(nit: str) -> str:
    """Remove any non-digit characters from NIT."""
    return "".join(c for c in str(nit) if c.isdigit())


def generar_cufe(
    numero_factura: str,
    fecha_emision: datetime | str,
    nit_emisor: str,
    nit_adquiriente: str,
    total_sin_impuestos: Decimal | float | int,
    total_con_impuestos: Decimal | float | int,
    clave_tecnica: str,
    tipo_documento: str = "01",
) -> str:
    """
    Generates CUFE for Factura Electrónica de Venta.

    Args:
        numero_factura: Full invoice number with prefix (e.g., "SETP1")
        fecha_emision: Invoice issue date (datetime or ISO string)
        nit_emisor: Seller's NIT (digits only)
        nit_adquiriente: Buyer's NIT (digits only)
        total_sin_impuestos: Total without taxes (base)
        total_con_impuestos: Total with taxes
        clave_tecnica: Technical key from DIAN resolution
        tipo_documento: Document type code ("01" = Factura Electrónica)

    Returns:
        96-character CUFE hex string
    """
    raw = (
        numero_factura
        + _fmt_dian_date(fecha_emision)
        + _clean_nit(nit_emisor)
        + _clean_nit(nit_adquiriente)
        + _digits(total_sin_impuestos)
        + _digits(total_con_impuestos)
        + clave_tecnica
        + tipo_documento
    )
    return hashlib.sha384(raw.encode("utf-8")).hexdigest().upper()


def generar_cude(
    numero_documento: str,
    fecha_emision: datetime | str,
    nit_emisor: str,
    nit_adquiriente: str,
    total_sin_impuestos: Decimal | float | int,
    total_con_impuestos: Decimal | float | int,
    clave_tecnica: str,
    tipo_documento: str = "04",
) -> str:
    """
    Generates CUDE for Nota Crédito / Nota Débito.

    Args:
        tipo_documento: "04" = Nota Crédito, "05" = Nota Débito
    """
    raw = (
        numero_documento
        + _fmt_dian_date(fecha_emision)
        + _clean_nit(nit_emisor)
        + _clean_nit(nit_adquiriente)
        + _digits(total_sin_impuestos)
        + _digits(total_con_impuestos)
        + clave_tecnica
        + tipo_documento
    )
    return hashlib.sha384(raw.encode("utf-8")).hexdigest().upper()


def generar_cufe_dee_pos(
    numero_documento: str,
    fecha_emision: datetime | str,
    nit_emisor: str,
    total_con_impuestos: Decimal | float | int,
    clave_tecnica: str,
    nit_adquiriente: str = "222222222222",
) -> str:
    """
    Generates CUFE for DEE POS (Documento Equivalente Electrónico - Tiquete POS).
    For DEE POS, when no buyer NIT, DIAN standard uses "222222222222" as default.
    """
    return generar_cufe(
        numero_factura=numero_documento,
        fecha_emision=fecha_emision,
        nit_emisor=nit_emisor,
        nit_adquiriente=nit_adquiriente,
        total_sin_impuestos=total_con_impuestos,
        total_con_impuestos=total_con_impuestos,
        clave_tecnica=clave_tecnica,
        tipo_documento="01",
    )
