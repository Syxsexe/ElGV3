"""
modules/documentos.py — El G POS
Documentos comerciales: cotizaciones, órdenes de pedido y remisiones.

Comparten estructura (cabecera + ítems) y trazabilidad entre sí:
    cotización → orden de pedido → remisión → venta/factura

No modifican stock: son documentos previos o paralelos a la venta. El
descuento del inventario ocurre al facturar (registrar_venta).
"""

from datetime import datetime

from database import get_connection
from auth import get_usuario_id
from modules.inventario import obtener_producto

IVA_POR_DEFECTO = 0.19

# Metadatos por tipo de documento
TIPOS = {
    "cotizacion":   {"prefijo": "COT", "label": "Cotización",     "titulo": "COTIZACION"},
    "orden_pedido": {"prefijo": "OP",  "label": "Orden de Pedido", "titulo": "ORDEN DE PEDIDO"},
    "remision":     {"prefijo": "REM", "label": "Remisión",        "titulo": "REMISION"},
}

# Conversión permitida: de un tipo se puede generar el siguiente en la cadena.
_SIGUIENTE = {
    "cotizacion":   "orden_pedido",
    "orden_pedido": "remision",
    "remision":     None,
}


def _generar_numero(conn, tipo: str) -> str:
    """Genera un número único por tipo, ej: COT-20260706-0001."""
    prefijo = TIPOS[tipo]["prefijo"]
    hoy = datetime.now().strftime("%Y%m%d")
    patron = f"{prefijo}-{hoy}-%"
    fila = conn.execute(
        "SELECT COUNT(*) FROM documentos_comerciales WHERE numero LIKE ?",
        (patron,)
    ).fetchone()
    secuencia = (fila[0] or 0) + 1
    return f"{prefijo}-{hoy}-{secuencia:04d}"


def _normalizar_item(item: dict) -> dict:
    """
    Normaliza un ítem de entrada a la forma persistible.
    item puede venir como:
        {"tipo": "producto", "id": 5, "cantidad": 2}                      -> toma precio/nombre del producto
        {"tipo": "producto", "id": 5, "cantidad": 2, "precio_unit": 9000} -> precio manual
        {"tipo": "combo",    "id": 3, "cantidad": 1}
        {"tipo": "libre", "descripcion": "Servicio X", "cantidad": 1, "precio_unit": 50000}
    """
    tipo = item.get("tipo", "producto")
    cantidad = float(item["cantidad"])
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor a 0.")

    producto_id = None
    combo_id = None
    descripcion = item.get("descripcion", "")
    precio_unit = item.get("precio_unit")

    if tipo == "producto":
        producto = obtener_producto(item["id"])
        if not producto:
            raise ValueError(f"Producto ID {item['id']} no encontrado.")
        producto_id = producto["id"]
        descripcion = descripcion or producto["nombre"]
        if precio_unit is None:
            precio_unit = producto["precio_venta"]
    elif tipo == "combo":
        conn = get_connection()
        combo = conn.execute(
            "SELECT * FROM combos WHERE id = ?", (item["id"],)
        ).fetchone()
        conn.close()
        if not combo:
            raise ValueError(f"Combo ID {item['id']} no encontrado.")
        combo_id = combo["id"]
        descripcion = descripcion or combo["nombre"]
        if precio_unit is None:
            precio_unit = combo["precio"]
    elif tipo == "libre":
        if not descripcion:
            raise ValueError("Los ítems de texto libre requieren descripción.")
        if precio_unit is None:
            raise ValueError("Los ítems de texto libre requieren precio.")
    else:
        raise ValueError(f"Tipo de ítem inválido: {tipo}")

    precio_unit = float(precio_unit)
    return {
        "producto_id": producto_id,
        "combo_id": combo_id,
        "descripcion": descripcion,
        "cantidad": cantidad,
        "precio_unit": precio_unit,
        "subtotal": round(cantidad * precio_unit, 2),
    }


def crear_documento(
    tipo: str,
    items: list[dict],
    cliente_id: int = None,
    descuento: float = 0,
    iva_porcentaje: float = 0,
    vigencia: str = None,
    notas: str = None,
    doc_origen_id: int = None,
) -> int:
    """
    Crea un documento comercial (cotización, orden de pedido o remisión).
    Retorna el ID generado.

    iva_porcentaje: 0 = documento sin IVA discriminado (POS simple);
                    0.19 = discrimina IVA sobre el subtotal.
    """
    if tipo not in TIPOS:
        raise ValueError(f"Tipo de documento inválido: {tipo}")
    if not items:
        raise ValueError("El documento no tiene ítems.")

    items_norm = [_normalizar_item(i) for i in items]
    subtotal = round(sum(i["subtotal"] for i in items_norm), 2)
    descuento = max(0, float(descuento or 0))
    base = max(0, subtotal - descuento)
    iva = round(base * iva_porcentaje, 2) if iva_porcentaje else 0.0
    total = round(base + iva, 2)

    conn = get_connection()
    try:
        numero = _generar_numero(conn, tipo)
        cur = conn.execute("""
            INSERT INTO documentos_comerciales
                (tipo, numero, cliente_id, fecha, vigencia, estado,
                 subtotal, descuento, iva_porcentaje, iva, total,
                 usuario_id, doc_origen_id, notas)
            VALUES (?, ?, ?, datetime('now','localtime'), ?, 'vigente',
                    ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            tipo, numero, cliente_id, vigencia,
            subtotal, descuento, iva_porcentaje, iva, total,
            get_usuario_id(), doc_origen_id, notas,
        ))
        doc_id = cur.lastrowid

        for it in items_norm:
            conn.execute("""
                INSERT INTO documento_items
                    (documento_id, producto_id, combo_id, descripcion,
                     cantidad, precio_unit, subtotal)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                doc_id, it["producto_id"], it["combo_id"], it["descripcion"],
                it["cantidad"], it["precio_unit"], it["subtotal"],
            ))

        conn.commit()

        try:
            from modules.auditoria import registrar
            registrar(
                "documento",
                f"{TIPOS[tipo]['label']} {numero} creada — total: ${total:,.0f}",
                referencia_id=doc_id,
            )
        except Exception:
            pass

        return doc_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_documento(doc_id: int) -> dict | None:
    """Retorna un documento con su detalle de ítems y datos del cliente."""
    conn = get_connection()
    doc = conn.execute("""
        SELECT d.*, u.usuario AS creado_por,
               c.nombre AS cliente_nombre, c.tipo_documento AS cliente_tipo_doc,
               c.documento AS cliente_documento, c.direccion AS cliente_direccion,
               c.telefono AS cliente_telefono, c.email AS cliente_email
        FROM documentos_comerciales d
        JOIN usuarios u ON d.usuario_id = u.id
        LEFT JOIN clientes c ON d.cliente_id = c.id
        WHERE d.id = ?
    """, (doc_id,)).fetchone()

    if not doc:
        conn.close()
        return None

    items = conn.execute(
        "SELECT * FROM documento_items WHERE documento_id = ? ORDER BY id",
        (doc_id,)
    ).fetchall()
    conn.close()
    return {**dict(doc), "items": [dict(i) for i in items]}


def listar_documentos(
    tipo: str = None,
    estado: str = None,
    cliente_id: int = None,
    limite: int = 200,
) -> list:
    """Lista documentos con filtros opcionales, más recientes primero."""
    conn = get_connection()
    query = """
        SELECT d.*, c.nombre AS cliente_nombre
        FROM documentos_comerciales d
        LEFT JOIN clientes c ON d.cliente_id = c.id
        WHERE 1=1
    """
    params = []
    if tipo:
        query += " AND d.tipo = ?"
        params.append(tipo)
    if estado:
        query += " AND d.estado = ?"
        params.append(estado)
    if cliente_id:
        query += " AND d.cliente_id = ?"
        params.append(cliente_id)
    query += " ORDER BY d.fecha DESC, d.id DESC LIMIT ?"
    params.append(limite)

    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def cambiar_estado(doc_id: int, estado: str) -> bool:
    """Cambia el estado de un documento."""
    validos = {"vigente", "aceptada", "rechazada", "facturada", "entregada", "anulada"}
    if estado not in validos:
        raise ValueError(f"Estado inválido: {estado}")
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE documentos_comerciales SET estado = ? WHERE id = ?",
            (estado, doc_id)
        )
        conn.commit()
        return True
    finally:
        conn.close()


def anular_documento(doc_id: int) -> bool:
    """Marca un documento como anulado (no se elimina, para trazabilidad)."""
    return cambiar_estado(doc_id, "anulada")


def convertir_documento(doc_id: int, nuevo_tipo: str = None) -> int:
    """
    Genera un nuevo documento del siguiente tipo en la cadena a partir de uno
    existente, copiando sus ítems y enlazando la trazabilidad (doc_origen_id).

    cotización → orden de pedido → remisión

    Si nuevo_tipo es None, usa el siguiente natural en la cadena.
    Retorna el ID del nuevo documento.
    """
    doc = obtener_documento(doc_id)
    if not doc:
        raise ValueError(f"Documento ID {doc_id} no encontrado.")

    if nuevo_tipo is None:
        nuevo_tipo = _SIGUIENTE.get(doc["tipo"])
    if not nuevo_tipo:
        raise ValueError(f"No hay conversión disponible para {doc['tipo']}.")

    items = [
        {
            "tipo": ("producto" if it["producto_id"]
                     else "combo" if it["combo_id"] else "libre"),
            "id": it["producto_id"] or it["combo_id"],
            "descripcion": it["descripcion"],
            "cantidad": it["cantidad"],
            "precio_unit": it["precio_unit"],
        }
        for it in doc["items"]
    ]

    nuevo_id = crear_documento(
        nuevo_tipo,
        items,
        cliente_id=doc["cliente_id"],
        descuento=doc["descuento"],
        iva_porcentaje=doc["iva_porcentaje"],
        notas=doc["notas"],
        doc_origen_id=doc_id,
    )

    # El documento origen queda "aceptada" (cotización→orden) o "entregada"
    # (orden→remisión); ambos indican que avanzó en la cadena.
    origen_estado = "aceptada" if doc["tipo"] == "cotizacion" else "entregada"
    cambiar_estado(doc_id, origen_estado)
    return nuevo_id


def cargar_en_carrito(doc_id: int):
    """
    Construye un Carrito de ventas a partir de un documento, para facturarlo.
    Ignora ítems de texto libre (no vinculados a producto/combo) y avisa.
    Retorna (carrito, omitidos) donde omitidos es la lista de descripciones
    de ítems que no se pudieron cargar.
    """
    from modules.ventas import Carrito

    doc = obtener_documento(doc_id)
    if not doc:
        raise ValueError(f"Documento ID {doc_id} no encontrado.")

    carrito = Carrito()
    omitidos = []
    for it in doc["items"]:
        try:
            if it["producto_id"]:
                carrito.agregar_producto(it["producto_id"], it["cantidad"])
            elif it["combo_id"]:
                carrito.agregar_combo(it["combo_id"], it["cantidad"])
            else:
                omitidos.append(it["descripcion"])
        except ValueError as e:
            omitidos.append(f"{it['descripcion']} ({e})")
    return carrito, omitidos


def marcar_facturado(doc_id: int, venta_id: int) -> bool:
    """Enlaza un documento con la venta que lo facturó y lo marca 'facturada'."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE documentos_comerciales SET estado = 'facturada', venta_id = ? WHERE id = ?",
            (venta_id, doc_id)
        )
        conn.commit()
        return True
    finally:
        conn.close()
