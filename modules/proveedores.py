"""
modules/proveedores.py — El G POS
Gestión de proveedores y pedidos de stock.
Al marcar un pedido como recibido, suma automáticamente al stock
de productos (tienda) o insumos (cocina).
"""

from database import get_connection
from auth import get_usuario_id


def migrar_egresos():
    """Crea la tabla de egresos si no existe y aplica migraciones incrementales."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS egresos (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha       TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            concepto    TEXT    NOT NULL,
            total       REAL    NOT NULL CHECK(total > 0),
            metodo_pago TEXT    NOT NULL DEFAULT 'efectivo'
                            CHECK(metodo_pago IN
                                ('efectivo','transferencia','tarjeta','nequi','daviplata','mixto')),
            sesion_id   INTEGER REFERENCES sesiones_caja(id),
            pedido_id   INTEGER REFERENCES pedidos(id),
            usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
            notas       TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pagos_egreso (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            egreso_id INTEGER NOT NULL REFERENCES egresos(id) ON DELETE CASCADE,
            metodo    TEXT    NOT NULL,
            monto     REAL    NOT NULL CHECK(monto > 0)
        )
    """)
    # Migración: columna categoria (gastos generales)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(egresos)").fetchall()]
    if "categoria" not in cols:
        conn.execute("ALTER TABLE egresos ADD COLUMN categoria TEXT DEFAULT 'Otros'")
    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════════
# PROVEEDORES
# ════════════════════════════════════════════════════════════

def listar_proveedores(solo_activos: bool = True) -> list:
    conn  = get_connection()
    query = "SELECT * FROM proveedores"
    if solo_activos:
        query += " WHERE activo = 1"
    query += " ORDER BY nombre"
    filas = conn.execute(query).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def obtener_proveedor(proveedor_id: int) -> dict | None:
    conn = get_connection()
    fila = conn.execute(
        "SELECT * FROM proveedores WHERE id = ?", (proveedor_id,)
    ).fetchone()
    conn.close()
    return dict(fila) if fila else None


def crear_proveedor(nombre: str, contacto: str = None,
                    telefono: str = None, email: str = None) -> int:
    """Crea un proveedor. Retorna el ID generado."""
    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO proveedores (nombre, contacto, telefono, email)
            VALUES (?, ?, ?, ?)
        """, (nombre.strip(), contacto, telefono, email))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def editar_proveedor(proveedor_id: int, **campos) -> bool:
    permitidos = {"nombre", "contacto", "telefono", "email", "activo"}
    campos_validos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos_validos:
        return False
    set_clause = ", ".join(f"{k} = ?" for k in campos_validos)
    valores    = list(campos_validos.values()) + [proveedor_id]
    conn = get_connection()
    try:
        conn.execute(f"UPDATE proveedores SET {set_clause} WHERE id = ?", valores)
        conn.commit()
        return True
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════
# PEDIDOS
# ════════════════════════════════════════════════════════════

def listar_pedidos(estado: str = None, proveedor_id: int = None,
                   limite: int = 50) -> list:
    """
    Lista pedidos con info del proveedor y totales.
    estado: 'pendiente' | 'recibido' | 'cancelado' | None (todos)
    """
    conn   = get_connection()
    query  = """
        SELECT p.*, pr.nombre AS proveedor_nombre,
               COUNT(dp.id) AS num_items
        FROM pedidos p
        JOIN proveedores pr ON p.proveedor_id = pr.id
        LEFT JOIN detalle_pedido dp ON dp.pedido_id = p.id
        WHERE 1=1
    """
    params = []
    if estado:
        query += " AND p.estado = ?"
        params.append(estado)
    if proveedor_id:
        query += " AND p.proveedor_id = ?"
        params.append(proveedor_id)
    query += " GROUP BY p.id ORDER BY p.fecha DESC LIMIT ?"
    params.append(limite)
    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def obtener_pedido(pedido_id: int) -> dict | None:
    """Retorna un pedido con su detalle completo."""
    conn   = get_connection()
    pedido = conn.execute("""
        SELECT p.*, pr.nombre AS proveedor_nombre
        FROM pedidos p
        JOIN proveedores pr ON p.proveedor_id = pr.id
        WHERE p.id = ?
    """, (pedido_id,)).fetchone()

    if not pedido:
        conn.close()
        return None

    detalle = conn.execute("""
        SELECT dp.*,
               COALESCE(prod.nombre, ins.nombre) AS item_nombre,
               CASE WHEN dp.producto_id IS NOT NULL THEN 'producto'
                    ELSE 'insumo' END AS item_tipo,
               COALESCE(prod.precio_costo, 0) AS costo_actual
        FROM detalle_pedido dp
        LEFT JOIN productos prod ON dp.producto_id = prod.id
        LEFT JOIN insumos   ins  ON dp.insumo_id   = ins.id
        WHERE dp.pedido_id = ?
        ORDER BY dp.id
    """, (pedido_id,)).fetchall()

    conn.close()
    return {
        **dict(pedido),
        "detalle": [dict(d) for d in detalle]
    }


def crear_pedido(proveedor_id: int, items: list[dict],
                 notas: str = None) -> int:
    """
    Crea un pedido en estado 'pendiente'.

    items: [
        {"producto_id": 1, "cantidad": 10, "precio_unit": 9000},
        {"insumo_id":   3, "cantidad": 3000, "precio_unit": 0},
    ]
    Retorna el ID del pedido.
    """
    if not items:
        raise ValueError("El pedido debe tener al menos un ítem.")

    total = sum(i.get("cantidad", 0) * i.get("precio_unit", 0) for i in items)

    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO pedidos (proveedor_id, estado, total, notas)
            VALUES (?, 'pendiente', ?, ?)
        """, (proveedor_id, total, notas))
        pedido_id = cur.lastrowid

        for item in items:
            conn.execute("""
                INSERT INTO detalle_pedido
                    (pedido_id, producto_id, insumo_id, cantidad, precio_unit)
                VALUES (?, ?, ?, ?, ?)
            """, (
                pedido_id,
                item.get("producto_id"),
                item.get("insumo_id"),
                item["cantidad"],
                item.get("precio_unit", 0),
            ))

        conn.commit()
        return pedido_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def recibir_pedido(pedido_id: int, pagos: list[dict] = None,
                   sesion_id: int = None) -> dict:
    """
    Marca el pedido como recibido, suma el stock automáticamente
    y registra el egreso en caja si hay pagos.

    pagos: [{"metodo": "efectivo", "monto": 50000}, ...]
           Si es None no se registra egreso.
    sesion_id: ID de la sesión de caja activa.
    """
    migrar_egresos()
    pedido = obtener_pedido(pedido_id)
    if not pedido:
        raise ValueError("Pedido no encontrado.")
    if pedido["estado"] != "pendiente":
        raise ValueError(f"El pedido ya está en estado '{pedido['estado']}'.")

    from modules.inventario import actualizar_stock, recalcular_costos_cocina

    conn = get_connection()
    try:
        actualizados = []
        costo_insumo_cambio = False
        for item in pedido["detalle"]:
            precio_unit = item.get("precio_unit", 0) or 0

            if item["producto_id"]:
                # Producto de tienda: inventario real → sumar stock
                actualizar_stock(item["producto_id"], item["cantidad"], conn=conn)
                # Actualizar precio de costo si se ingresó uno
                if precio_unit > 0:
                    conn.execute(
                        "UPDATE productos SET precio_costo = ? WHERE id = ?",
                        (precio_unit, item["producto_id"])
                    )
                actualizados.append({
                    "nombre":   item["item_nombre"],
                    "tipo":     "producto",
                    "cantidad": item["cantidad"],
                    "nuevo_costo": precio_unit if precio_unit > 0 else None,
                })
            elif item["insumo_id"]:
                # Insumo de cocina: modelo de COSTO (no de stock). Recibir la compra
                # actualiza el costo por unidad = precio_unit (ya viene por-unidad
                # desde la presentación: total pagado ÷ cantidad comprada).
                if precio_unit > 0:
                    conn.execute(
                        "UPDATE insumos SET costo_unitario = ? WHERE id = ?",
                        (precio_unit, item["insumo_id"])
                    )
                    costo_insumo_cambio = True
                actualizados.append({
                    "nombre":   item["item_nombre"],
                    "tipo":     "insumo",
                    "cantidad": item["cantidad"],
                    "nuevo_costo": precio_unit if precio_unit > 0 else None,
                })

        # Si cambió el costo de algún insumo, propagar a los platos que lo usan.
        if costo_insumo_cambio:
            recalcular_costos_cocina(conn=conn)

        conn.execute("""
            UPDATE pedidos
            SET estado = 'recibido',
                fecha  = COALESCE(fecha, datetime('now','localtime'))
            WHERE id = ?
        """, (pedido_id,))

        # Registrar egreso si se indicaron pagos
        egreso_id = None
        if pagos:
            from datetime import datetime
            total_pagado = sum(p["monto"] for p in pagos)
            metodo_final = "mixto" if len(pagos) > 1 else pagos[0]["metodo"]
            fecha_ahora  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            cur_eg = conn.execute("""
                INSERT INTO egresos
                    (fecha, concepto, total, metodo_pago, sesion_id, pedido_id, usuario_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                fecha_ahora,
                f"Pago pedido #{pedido_id} — {pedido['proveedor_nombre']}",
                total_pagado, metodo_final,
                sesion_id, pedido_id, get_usuario_id()
            ))
            egreso_id = cur_eg.lastrowid

            for pago in pagos:
                conn.execute("""
                    INSERT INTO pagos_egreso (egreso_id, metodo, monto)
                    VALUES (?, ?, ?)
                """, (egreso_id, pago["metodo"], pago["monto"]))

            # Descontar de la sesión de caja activa
            if sesion_id:
                conn.execute("""
                    UPDATE sesiones_caja
                    SET total_ventas = total_ventas - ?
                    WHERE id = ?
                """, (total_pagado, sesion_id))

        conn.commit()
        return {
            "pedido_id":         pedido_id,
            "items_actualizados": actualizados,
            "egreso_id":         egreso_id,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def cancelar_pedido(pedido_id: int) -> bool:
    """Cancela un pedido pendiente sin modificar el stock."""
    conn = get_connection()
    try:
        pedido = conn.execute(
            "SELECT estado FROM pedidos WHERE id = ?", (pedido_id,)
        ).fetchone()
        if not pedido or pedido["estado"] != "pendiente":
            raise ValueError("Solo se pueden cancelar pedidos pendientes.")
        conn.execute(
            "UPDATE pedidos SET estado = 'cancelado' WHERE id = ?",
            (pedido_id,)
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════
# EGRESOS
# ════════════════════════════════════════════════════════════

def listar_egresos(fecha_inicio: str = None, fecha_fin: str = None,
                   limite: int = 50) -> list:
    """Retorna egresos registrados con detalle de pagos."""
    conn   = get_connection()
    query  = """
        SELECT e.*, u.usuario AS cajero,
               p.proveedor_id
        FROM egresos e
        JOIN usuarios u ON e.usuario_id = u.id
        LEFT JOIN pedidos p ON e.pedido_id = p.id
        WHERE 1=1
    """
    params = []
    if fecha_inicio:
        query += " AND date(e.fecha) >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND date(e.fecha) <= ?"
        params.append(fecha_fin)
    query += " ORDER BY e.fecha DESC LIMIT ?"
    params.append(limite)
    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


# ════════════════════════════════════════════════════════════
# PRUEBA DIRECTA
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from database import inicializar
    from auth import iniciar_sesion
    from modules.inventario import listar_productos, listar_insumos

    inicializar()
    iniciar_sesion("admin", "admin123")

    print("\n── Proveedores ──")
    provs = listar_proveedores()
    for p in provs:
        print(f"  {p['id']}. {p['nombre']} — {p['telefono']}")

    if not provs:
        pid = crear_proveedor("Dist. TCG Colombia", "Carlos", "3001234567")
        print(f"  Proveedor creado: ID {pid}")
        provs = listar_proveedores()

    prods  = listar_productos(tipo="tienda")
    insumos = listar_insumos()

    print("\n── Crear pedido con productos e insumos ──")
    items = []
    if prods:
        items.append({"producto_id": prods[0]["id"], "cantidad": 10, "precio_unit": 9000})
        print(f"  Producto: {prods[0]['nombre']} x10")
    if insumos:
        items.append({"insumo_id": insumos[0]["id"], "cantidad": 3000, "precio_unit": 0})
        print(f"  Insumo:   {insumos[0]['nombre']} x3000")

    pedido_id = crear_pedido(provs[0]["id"], items, notas="Pedido de prueba")
    print(f"  Pedido creado: ID {pedido_id}")

    print("\n── Recibir pedido ──")
    resultado = recibir_pedido(pedido_id)
    print(f"  Items actualizados: {len(resultado['items_actualizados'])}")
    for item in resultado["items_actualizados"]:
        print(f"    + {item['cantidad']} de {item['nombre']} ({item['tipo']})")

    print("\n── Historial de pedidos ──")
    for p in listar_pedidos():
        print(f"  [{p['estado']}] {p['proveedor_nombre']} — {p['num_items']} items")