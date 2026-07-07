"""
modules/compras.py — El G POS
Ingreso de compras: registro de facturas de proveedor (incluida factura
electrónica con CUFE) para el libro contable de compras.

Una compra puede estar enlazada a un pedido recibido (pedido_id) o registrarse
de forma independiente. El descuento de stock ocurre en la recepción del pedido
(modules.proveedores.recibir_pedido); aquí solo se registra el soporte contable.
"""

from datetime import datetime

from database import get_connection
from auth import get_usuario_id

TIPOS_DOCUMENTO = {
    "factura_electronica": "Factura Electrónica",
    "factura":             "Factura de papel",
    "pos":                 "Documento POS",
    "otro":                "Otro soporte",
}

METODOS_PAGO = ["efectivo", "transferencia", "nequi", "daviplata", "tarjeta", "credito"]


def migrar():
    """Crea la tabla compras_proveedor si no existe."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS compras_proveedor (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            proveedor_id   INTEGER NOT NULL REFERENCES proveedores(id),
            pedido_id      INTEGER REFERENCES pedidos(id),
            numero_factura TEXT    NOT NULL,
            tipo_documento TEXT    NOT NULL DEFAULT 'factura'
                               CHECK(tipo_documento IN ('factura_electronica','factura','pos','otro')),
            cufe           TEXT,
            fecha          TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            base           REAL    NOT NULL DEFAULT 0,
            iva            REAL    NOT NULL DEFAULT 0,
            total          REAL    NOT NULL DEFAULT 0,
            metodo_pago    TEXT,
            notas          TEXT,
            usuario_id     INTEGER REFERENCES usuarios(id),
            creado_en      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    conn.close()


def registrar_ingreso_compra(
    proveedor_id: int,
    numero_factura: str,
    base: float,
    iva: float = 0,
    tipo_documento: str = "factura",
    cufe: str = None,
    pedido_id: int = None,
    metodo_pago: str = "efectivo",
    fecha: str = None,
    notas: str = None,
) -> int:
    """
    Registra la factura de compra de un proveedor. Retorna el ID creado.
    total = base + iva.
    """
    migrar()
    numero_factura = (numero_factura or "").strip()
    if not numero_factura:
        raise ValueError("El número de factura es obligatorio.")
    if tipo_documento not in TIPOS_DOCUMENTO:
        raise ValueError(f"Tipo de documento inválido: {tipo_documento}")
    base = float(base or 0)
    iva = float(iva or 0)
    if base < 0 or iva < 0:
        raise ValueError("La base y el IVA no pueden ser negativos.")
    total = round(base + iva, 2)
    if total <= 0:
        raise ValueError("El total de la compra debe ser mayor a cero.")
    if tipo_documento == "factura_electronica" and not (cufe or "").strip():
        raise ValueError("Una factura electrónica requiere CUFE.")

    fecha = fecha or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO compras_proveedor
                (proveedor_id, pedido_id, numero_factura, tipo_documento, cufe,
                 fecha, base, iva, total, metodo_pago, notas, usuario_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            proveedor_id, pedido_id, numero_factura, tipo_documento,
            (cufe or "").strip() or None, fecha, round(base, 2), round(iva, 2),
            total, metodo_pago, notas, get_usuario_id(),
        ))
        compra_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    try:
        from modules.auditoria import registrar
        registrar(
            "compra",
            f"Ingreso de compra {numero_factura} — proveedor #{proveedor_id} — "
            f"${total:,.0f} ({TIPOS_DOCUMENTO[tipo_documento]})",
            referencia_id=compra_id,
        )
    except Exception:
        pass
    return compra_id


def listar_compras(
    fecha_inicio: str = None,
    fecha_fin: str = None,
    proveedor_id: int = None,
    limite: int = 300,
) -> list[dict]:
    """Lista facturas de compra con filtros opcionales."""
    migrar()
    conn = get_connection()
    query = """
        SELECT cp.*, pr.nombre AS proveedor_nombre
        FROM compras_proveedor cp
        JOIN proveedores pr ON cp.proveedor_id = pr.id
        WHERE 1=1
    """
    params = []
    if fecha_inicio:
        query += " AND date(cp.fecha) >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND date(cp.fecha) <= ?"
        params.append(fecha_fin)
    if proveedor_id:
        query += " AND cp.proveedor_id = ?"
        params.append(proveedor_id)
    query += " ORDER BY cp.fecha DESC, cp.id DESC LIMIT ?"
    params.append(limite)

    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def obtener_compra(compra_id: int) -> dict | None:
    """Retorna una factura de compra por ID."""
    migrar()
    conn = get_connection()
    fila = conn.execute("""
        SELECT cp.*, pr.nombre AS proveedor_nombre
        FROM compras_proveedor cp
        JOIN proveedores pr ON cp.proveedor_id = pr.id
        WHERE cp.id = ?
    """, (compra_id,)).fetchone()
    conn.close()
    return dict(fila) if fila else None
