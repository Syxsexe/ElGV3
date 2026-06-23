"""
modules/fiscal_documents.py — El G POS
Credit notes, debit notes and DEE POS generation for DIAN compliance.
"""

from datetime import datetime
from typing import Any

from database import get_connection
from auth import get_usuario_id


def crear_nota_credito(
    venta_id: int,
    motivo: str,
    items_anular: list[dict] = None,
    sesion_id: int = None,
) -> dict:
    """
    Creates a credit note for a sale.
    items_anular: specific items to reverse (None = full reversal).
    Returns credit note data ready for sync with backend.
    """
    conn = get_connection()
    venta = conn.execute(
        "SELECT * FROM ventas WHERE id = ?", (venta_id,)
    ).fetchone()

    if not venta:
        conn.close()
        raise ValueError(f"Venta ID {venta_id} no encontrada")

    detalle = conn.execute(
        "SELECT * FROM detalle_venta WHERE venta_id = ?", (venta_id,)
    ).fetchall()
    conn.close()

    venta = dict(venta)
    detalle = [dict(d) for d in detalle]

    if items_anular:
        subtotal = sum(
            d["subtotal"] for d in detalle
            if d["id"] in [i["detalle_id"] for i in items_anular]
        )
    else:
        subtotal = venta["total"]

    total_base = round(subtotal / 1.19, 2)
    iva = round(subtotal - total_base, 2)

    return {
        "tipo": "nota_credito",
        "venta_id_original": venta_id,
        "motivo": motivo,
        "fecha": datetime.now().isoformat(),
        "total_base": total_base,
        "iva": iva,
        "total": subtotal,
        "usuario_id": get_usuario_id(),
        "sesion_id": sesion_id,
        "items": detalle if not items_anular else items_anular,
        "anulacion_total": items_anular is None,
    }


def crear_nota_debito(
    venta_id: int,
    motivo: str,
    valor_adicional: float,
    sesion_id: int = None,
) -> dict:
    """
    Creates a debit note to increase the value of an existing sale.
    """
    conn = get_connection()
    venta = conn.execute(
        "SELECT * FROM ventas WHERE id = ?", (venta_id,)
    ).fetchone()
    conn.close()

    if not venta:
        raise ValueError(f"Venta ID {venta_id} no encontrada")

    total_base = round(valor_adicional / 1.19, 2)
    iva = round(valor_adicional - total_base, 2)

    return {
        "tipo": "nota_debito",
        "venta_id_original": venta_id,
        "motivo": motivo,
        "fecha": datetime.now().isoformat(),
        "total_base": total_base,
        "iva": iva,
        "total": valor_adicional,
        "usuario_id": get_usuario_id(),
        "sesion_id": sesion_id,
    }


def preparar_venta_para_dian(venta_data: dict, cliente: dict = None) -> dict:
    """
    Prepares sale data for DIAN electronic invoicing.
    Extracts required fields from the local sale structure.
    """
    return {
        "venta_id": venta_data["id"],
        "fecha": venta_data["fecha"],
        "total": venta_data["total"],
        "descuento": venta_data.get("descuento", 0),
        "metodo_pago": venta_data.get("metodo_pago", "efectivo"),
        "tipo": venta_data.get("tipo", "tienda"),
        "vendedor_id": venta_data.get("usuario_id"),
        "adquiriente": {
            "nit": cliente["documento"] if cliente else "222222222222",
            "razon_social": cliente["nombre"] if cliente else "CONSUMIDOR FINAL",
            "tipo_documento": cliente["tipo_documento"] if cliente else "CONSUMIDOR_FINAL",
            "email": cliente.get("email", "") if cliente else "",
            "direccion": cliente.get("direccion", "") if cliente else "",
            "telefono": cliente.get("telefono", "") if cliente else "",
        } if cliente else {
            "nit": "222222222222",
            "razon_social": "CONSUMIDOR FINAL",
            "tipo_documento": "CONSUMIDOR_FINAL",
        },
        "items": venta_data.get("detalle", []),
        "pagos": venta_data.get("pagos", []),
    }
