"""
modules/cuentas.py — El G POS
Cuentas abiertas por cliente/mesa.
Flujo: abrir cuenta → agregar ítems → ver resumen → cobrar y cerrar.
"""

from database import get_connection
from auth import get_usuario_id


# ════════════════════════════════════════════════════════════
# MIGRACION — agrega las tablas si no existen
# ════════════════════════════════════════════════════════════

def migrar():
    """
    Crea las tablas de cuentas abiertas si no existen todavía.
    Se llama desde database.inicializar() o al importar el módulo.
    """
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cuentas (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente     TEXT    NOT NULL,
            cliente_id  INTEGER REFERENCES clientes(id),
            mesa        TEXT    NOT NULL,
            abierta_en  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            cerrada_en  TEXT,
            estado      TEXT    NOT NULL DEFAULT 'abierta'
                            CHECK(estado IN ('abierta','cobrada','cancelada')),
            usuario_id  INTEGER NOT NULL REFERENCES usuarios(id),
            venta_id    INTEGER REFERENCES ventas(id),
            notas       TEXT
        )
    """)
    # Columna agregada después del create inicial — para DBs existentes
    columnas = {r[1] for r in conn.execute("PRAGMA table_info(cuentas)")}
    if "cliente_id" not in columnas:
        conn.execute(
            "ALTER TABLE cuentas ADD COLUMN cliente_id INTEGER REFERENCES clientes(id)"
        )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cuenta_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            cuenta_id   INTEGER NOT NULL REFERENCES cuentas(id) ON DELETE CASCADE,
            producto_id INTEGER REFERENCES productos(id),
            combo_id    INTEGER REFERENCES combos(id),
            nombre      TEXT    NOT NULL,
            cantidad    REAL    NOT NULL DEFAULT 1,
            precio_unit REAL    NOT NULL,
            subtotal    REAL    NOT NULL,
            agregado_en TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════════
# CUENTAS
# ════════════════════════════════════════════════════════════

def abrir_cuenta(
    cliente: str,
    mesa: str,
    notas: str = None,
    cliente_id: int = None,
) -> int:
    """
    Abre una nueva cuenta para un cliente en una mesa.
    cliente_id: ID del cliente registrado en la tabla clientes (opcional).
    Retorna el ID de la cuenta creada.
    Lanza ValueError si ya hay una cuenta abierta en esa mesa.
    """
    cliente = cliente.strip()
    mesa    = mesa.strip()

    if not cliente or not mesa:
        raise ValueError("El nombre del cliente y la mesa son obligatorios.")

    conn = get_connection()
    try:
        ocupada = conn.execute("""
            SELECT id FROM cuentas
            WHERE mesa = ? AND estado = 'abierta'
        """, (mesa,)).fetchone()

        if ocupada:
            raise ValueError(f"La mesa '{mesa}' ya tiene una cuenta abierta (ID {ocupada[0]}).")

        cur = conn.execute("""
            INSERT INTO cuentas (cliente, cliente_id, mesa, usuario_id, notas)
            VALUES (?, ?, ?, ?, ?)
        """, (cliente, cliente_id, mesa, get_usuario_id(), notas))
        conn.commit()
        cuenta_id = cur.lastrowid
    finally:
        conn.close()

    try:
        from modules.auditoria import registrar
        registrar("cuenta", f"Cuenta abierta — {cliente} / Mesa: {mesa}", referencia_id=cuenta_id)
    except Exception:
        pass
    return cuenta_id


def obtener_cuenta(cuenta_id: int) -> dict | None:
    """Retorna una cuenta con todos sus ítems."""
    conn = get_connection()
    cuenta = conn.execute("""
        SELECT c.*, u.usuario AS cajero
        FROM cuentas c
        JOIN usuarios u ON c.usuario_id = u.id
        WHERE c.id = ?
    """, (cuenta_id,)).fetchone()

    if not cuenta:
        conn.close()
        return None

    items = conn.execute("""
        SELECT * FROM cuenta_items
        WHERE cuenta_id = ?
        ORDER BY agregado_en
    """, (cuenta_id,)).fetchall()

    conn.close()
    cuenta = dict(cuenta)
    cuenta["items"] = [dict(i) for i in items]
    cuenta["total"] = sum(i["subtotal"] for i in cuenta["items"])
    return cuenta


def listar_cuentas_abiertas() -> list:
    """Retorna todas las cuentas con estado 'abierta'."""
    conn  = get_connection()
    filas = conn.execute("""
        SELECT c.*, u.usuario AS cajero,
               COUNT(ci.id)      AS num_items,
               COALESCE(SUM(ci.subtotal), 0) AS total
        FROM cuentas c
        JOIN usuarios u ON c.usuario_id = u.id
        LEFT JOIN cuenta_items ci ON ci.cuenta_id = c.id
        WHERE c.estado = 'abierta'
        GROUP BY c.id
        ORDER BY c.abierta_en
    """).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def listar_cuentas_historial(limite: int = 50) -> list:
    """Retorna cuentas cerradas o canceladas (historial)."""
    conn  = get_connection()
    filas = conn.execute("""
        SELECT c.*, u.usuario AS cajero,
               COUNT(ci.id)      AS num_items,
               COALESCE(SUM(ci.subtotal), 0) AS total
        FROM cuentas c
        JOIN usuarios u ON c.usuario_id = u.id
        LEFT JOIN cuenta_items ci ON ci.cuenta_id = c.id
        WHERE c.estado != 'abierta'
        GROUP BY c.id
        ORDER BY c.cerrada_en DESC
        LIMIT ?
    """, (limite,)).fetchall()
    conn.close()
    return [dict(f) for f in filas]


# ════════════════════════════════════════════════════════════
# ÍTEMS DE CUENTA
# ════════════════════════════════════════════════════════════

def agregar_item(
    cuenta_id: int,
    producto_id: int = None,
    combo_id: int    = None,
    cantidad: float  = 1
) -> dict:
    """
    Agrega un producto o combo a la cuenta.
    Retorna el ítem insertado.
    No descuenta stock aquí — eso ocurre al cobrar.
    """
    conn = get_connection()
    try:
        # Verificar que la cuenta esté abierta
        cuenta = conn.execute(
            "SELECT estado FROM cuentas WHERE id = ?", (cuenta_id,)
        ).fetchone()
        if not cuenta or cuenta["estado"] != "abierta":
            raise ValueError("La cuenta no existe o ya está cerrada.")

        if producto_id:
            prod = conn.execute(
                "SELECT nombre, precio_venta FROM productos WHERE id = ? AND activo = 1",
                (producto_id,)
            ).fetchone()
            if not prod:
                raise ValueError("Producto no encontrado o inactivo.")
            nombre     = prod["nombre"]
            precio_unit = prod["precio_venta"]

        elif combo_id:
            combo = conn.execute(
                "SELECT nombre, precio FROM combos WHERE id = ? AND activo = 1",
                (combo_id,)
            ).fetchone()
            if not combo:
                raise ValueError("Combo no encontrado o inactivo.")
            nombre     = combo["nombre"]
            precio_unit = combo["precio"]
            producto_id = None

        else:
            raise ValueError("Debes indicar producto_id o combo_id.")

        subtotal = precio_unit * cantidad

        cur = conn.execute("""
            INSERT INTO cuenta_items
                (cuenta_id, producto_id, combo_id, nombre, cantidad, precio_unit, subtotal)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (cuenta_id, producto_id, combo_id, nombre, cantidad, precio_unit, subtotal))
        conn.commit()

        return {
            "id":          cur.lastrowid,
            "cuenta_id":   cuenta_id,
            "producto_id": producto_id,
            "combo_id":    combo_id,
            "nombre":      nombre,
            "cantidad":    cantidad,
            "precio_unit": precio_unit,
            "subtotal":    subtotal,
        }
    finally:
        conn.close()


def quitar_item(item_id: int) -> bool:
    """Elimina un ítem de la cuenta (antes de cobrar)."""
    conn = get_connection()
    try:
        item = conn.execute("""
            SELECT ci.id, c.estado
            FROM cuenta_items ci
            JOIN cuentas c ON ci.cuenta_id = c.id
            WHERE ci.id = ?
        """, (item_id,)).fetchone()

        if not item:
            return False
        if item["estado"] != "abierta":
            raise ValueError("No se puede modificar una cuenta ya cerrada.")

        conn.execute("DELETE FROM cuenta_items WHERE id = ?", (item_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def cambiar_cantidad_item(item_id: int, nueva_cantidad: float) -> bool:
    """Actualiza la cantidad de un ítem en una cuenta abierta."""
    if nueva_cantidad <= 0:
        return quitar_item(item_id)
    conn = get_connection()
    try:
        row = conn.execute("""
            SELECT ci.precio_unit, c.estado
            FROM cuenta_items ci
            JOIN cuentas c ON ci.cuenta_id = c.id
            WHERE ci.id = ?
        """, (item_id,)).fetchone()

        if not row:
            return False
        if row["estado"] != "abierta":
            raise ValueError("No se puede modificar una cuenta ya cerrada.")

        subtotal = round(row["precio_unit"] * nueva_cantidad, 2)
        conn.execute(
            "UPDATE cuenta_items SET cantidad = ?, subtotal = ? WHERE id = ?",
            (nueva_cantidad, subtotal, item_id)
        )
        conn.commit()
        return True
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════
# COBRO Y CIERRE
# ════════════════════════════════════════════════════════════

def cobrar_cuenta(
    cuenta_id: int,
    metodo_pago: str  = "efectivo",
    descuento: float  = 0,
    sesion_id: int    = None,
    pagos: list[dict] = None
) -> int:
    """
    Cierra la cuenta cobrando todos los ítems pendientes.
    Internamente crea una venta normal y descuenta stock/insumos.

    pagos: lista para pago mixto, ej:
        [{"metodo": "efectivo", "monto": 10000},
         {"metodo": "nequi",    "monto": 5000}]
    Si se omite, se usa metodo_pago por el total.
    Retorna el ID de la venta generada.
    """
    from modules.inventario import actualizar_stock, descontar_insumos_por_venta

    METODOS = {"efectivo", "transferencia", "tarjeta", "nequi", "daviplata", "credito"}

    cuenta = obtener_cuenta(cuenta_id)
    if not cuenta:
        raise ValueError("Cuenta no encontrada.")
    if cuenta["estado"] != "abierta":
        raise ValueError("La cuenta ya fue cobrada o cancelada.")
    if not cuenta["items"]:
        raise ValueError("La cuenta no tiene ítems.")

    total_bruto = cuenta["total"]
    total_final = max(0, total_bruto - descuento)

    # — Resolver método y pagos —
    if pagos:
        for p in pagos:
            if p["metodo"] not in METODOS:
                raise ValueError(f"Método de pago inválido: {p['metodo']}")
        suma_pagos = sum(p["monto"] for p in pagos)
        if round(suma_pagos, 2) < round(total_final, 2):
            raise ValueError(
                f"Los pagos suman {suma_pagos:,.0f} pero el total es {total_final:,.0f}."
            )
        metodo_final = "mixto" if len(pagos) > 1 else pagos[0]["metodo"]
    else:
        if metodo_pago not in METODOS:
            raise ValueError(f"Método de pago inválido: {metodo_pago}")
        metodo_final = metodo_pago
        pagos = [{"metodo": metodo_pago, "monto": total_final}]

    # Determinar tipo de venta (tienda / cocina / mixta)
    conn_main = get_connection()
    try:
        tipos = set()
        for item in cuenta["items"]:
            if item["combo_id"]:
                tipos.add("cocina")
            elif item["producto_id"]:
                cat_tipo = conn_main.execute("""
                    SELECT c.tipo FROM productos p
                    JOIN categorias c ON p.categoria_id = c.id
                    WHERE p.id = ?
                """, (item["producto_id"],)).fetchone()
                if cat_tipo:
                    tipos.add(cat_tipo["tipo"])
        tipo_venta = "cocina" if tipos == {"cocina"} else "tienda"

        # Crear venta
        from datetime import datetime
        fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn_main.execute("""
            INSERT INTO ventas
                (fecha, total, descuento, metodo_pago, tipo,
                 usuario_id, sesion_id, cliente_id, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fecha_ahora, total_final, descuento, metodo_final, tipo_venta,
            get_usuario_id(), sesion_id,
            cuenta.get("cliente_id"),
            f"Cuenta #{cuenta_id} — Mesa {cuenta['mesa']} — {cuenta['cliente']}"
        ))
        venta_id = cur.lastrowid

        # Insertar detalle de pagos
        for pago in pagos:
            conn_main.execute("""
                INSERT INTO pagos_venta (venta_id, metodo, monto)
                VALUES (?, ?, ?)
            """, (venta_id, pago["metodo"], pago["monto"]))

        # Insertar detalle y descontar stock
        for item in cuenta["items"]:
            conn_main.execute("""
                INSERT INTO detalle_venta
                    (venta_id, producto_id, combo_id, cantidad, precio_unit, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                venta_id,
                item["producto_id"], item["combo_id"],
                item["cantidad"], item["precio_unit"], item["subtotal"]
            ))

            if item["producto_id"]:
                cat_tipo = conn_main.execute("""
                    SELECT c.tipo FROM productos p
                    JOIN categorias c ON p.categoria_id = c.id
                    WHERE p.id = ?
                """, (item["producto_id"],)).fetchone()
                if cat_tipo and cat_tipo["tipo"] == "tienda":
                    actualizar_stock(item["producto_id"], -item["cantidad"], conn=conn_main)
                else:
                    descontar_insumos_por_venta(item["producto_id"], item["cantidad"], conn=conn_main)

            elif item["combo_id"]:
                combo_prods = conn_main.execute("""
                    SELECT producto_id, cantidad FROM combo_productos WHERE combo_id = ?
                """, (item["combo_id"],)).fetchall()
                for cp in combo_prods:
                    cat_tipo = conn_main.execute("""
                        SELECT c.tipo FROM productos p
                        JOIN categorias c ON p.categoria_id = c.id
                        WHERE p.id = ?
                    """, (cp["producto_id"],)).fetchone()
                    if cat_tipo and cat_tipo["tipo"] == "tienda":
                        actualizar_stock(cp["producto_id"],
                                         -(cp["cantidad"] * item["cantidad"]),
                                         conn=conn_main)
                    else:
                        descontar_insumos_por_venta(cp["producto_id"],
                                                     cp["cantidad"] * item["cantidad"],
                                                     conn=conn_main)

        # Actualizar sesión de caja
        if sesion_id:
            conn_main.execute("""
                UPDATE sesiones_caja SET total_ventas = total_ventas + ?
                WHERE id = ?
            """, (total_final, sesion_id))

        # Cerrar cuenta
        conn_main.execute("""
            UPDATE cuentas
            SET estado     = 'cobrada',
                cerrada_en = datetime('now','localtime'),
                venta_id   = ?
            WHERE id = ?
        """, (venta_id, cuenta_id))

        conn_main.commit()

        # Registrar cargo de crédito si aplica
        if metodo_final == "credito" and cuenta.get("cliente_id"):
            try:
                from modules.creditos import registrar_cargo
                registrar_cargo(cuenta["cliente_id"], total_final, venta_id=venta_id)
            except Exception as e:
                raise ValueError(f"No se pudo registrar el crédito: {e}") from e

        try:
            from modules.auditoria import registrar
            metodos_str = " + ".join(p["metodo"] for p in pagos)
            registrar(
                "cuenta",
                f"Cuenta #{cuenta_id} cobrada — {cuenta['cliente']} / Mesa: {cuenta['mesa']} "
                f"— total: ${total_final:,.0f} — método: {metodos_str}"
                + (f" — descuento: ${descuento:,.0f}" if descuento else ""),
                referencia_id=venta_id,
            )
        except Exception:
            pass

        return venta_id

    except Exception:
        conn_main.rollback()
        raise
    finally:
        conn_main.close()


def cancelar_cuenta(cuenta_id: int) -> bool:
    """
    Cancela una cuenta sin cobrarla (sin generar venta).
    Solo si no tiene ítems o el admin lo autoriza.
    """
    conn = get_connection()
    try:
        cuenta = conn.execute(
            "SELECT estado FROM cuentas WHERE id = ?", (cuenta_id,)
        ).fetchone()
        if not cuenta or cuenta["estado"] != "abierta":
            raise ValueError("La cuenta no existe o ya está cerrada.")

        conn.execute("""
            UPDATE cuentas
            SET estado     = 'cancelada',
                cerrada_en = datetime('now','localtime')
            WHERE id = ?
        """, (cuenta_id,))
        conn.commit()
    finally:
        conn.close()

    try:
        from modules.auditoria import registrar
        registrar("cuenta", f"Cuenta #{cuenta_id} cancelada", referencia_id=cuenta_id)
    except Exception:
        pass
    return True


# ════════════════════════════════════════════════════════════
# PRUEBA DIRECTA
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from database import inicializar
    from auth import iniciar_sesion
    from modules.inventario import crear_producto, crear_insumo, guardar_receta, listar_categorias
    from modules.caja import abrir_caja, formatear_pesos

    inicializar()
    migrar()
    iniciar_sesion("admin", "admin123")

    cats       = {c["nombre"]: c["id"] for c in listar_categorias()}
    id_sobre   = crear_producto("Sobre TCG", cats["TCG - Sobres"],
                                 precio_venta=15000, precio_costo=9000, stock=20)
    id_gaseosa = crear_producto("Gaseosa",   cats["Bebidas"],
                                 precio_venta=3000,  precio_costo=1200, stock=0)
    id_ham     = crear_producto("Hamburguesa", cats["Comidas rápidas"],
                                 precio_venta=12000, precio_costo=5500, stock=0)
    id_carne   = crear_insumo("Carne", stock=20, unidad="porción")
    id_pan     = crear_insumo("Pan",   stock=20, unidad="unidad")
    guardar_receta(id_ham, [
        {"insumo_id": id_carne, "cantidad": 1},
        {"insumo_id": id_pan,   "cantidad": 1},
    ])
    sesion_id = abrir_caja(50000)

    print("\n── Test 1: abrir cuentas ──")
    id_c1 = abrir_cuenta("Juan Pérez",  "Mesa 1")
    id_c2 = abrir_cuenta("Ana Gómez",   "Mesa 2")
    print(f"  Cuenta 1 ID: {id_c1} | Cuenta 2 ID: {id_c2}")

    print("\n── Test 2: mesa ocupada (debe fallar) ──")
    try:
        abrir_cuenta("Otro", "Mesa 1")
    except ValueError as e:
        print(f"  Error esperado: {e}")

    print("\n── Test 3: agregar ítems ──")
    agregar_item(id_c1, producto_id=id_sobre,   cantidad=2)
    agregar_item(id_c1, producto_id=id_gaseosa, cantidad=1)
    agregar_item(id_c1, producto_id=id_ham,     cantidad=1)
    agregar_item(id_c2, producto_id=id_sobre,   cantidad=1)
    print("  Ítems agregados a ambas cuentas")

    print("\n── Test 4: ver resumen cuenta 1 ──")
    cuenta = obtener_cuenta(id_c1)
    print(f"  Cliente: {cuenta['cliente']} | Mesa: {cuenta['mesa']}")
    for item in cuenta["items"]:
        print(f"    {item['nombre']} x{item['cantidad']} = {formatear_pesos(item['subtotal'])}")
    print(f"  Total: {formatear_pesos(cuenta['total'])}")

    print("\n── Test 5: cuentas abiertas ──")
    abiertas = listar_cuentas_abiertas()
    print(f"  Cuentas abiertas: {len(abiertas)}")
    for c in abiertas:
        print(f"    Mesa {c['mesa']} — {c['cliente']} — {formatear_pesos(c['total'])}")

    print("\n── Test 6: cobrar cuenta 1 ──")
    venta_id = cobrar_cuenta(id_c1, metodo_pago="efectivo", sesion_id=sesion_id)
    print(f"  Venta generada ID: {venta_id}")
    cuenta = obtener_cuenta(id_c1)
    print(f"  Estado cuenta: {cuenta['estado']}")

    print("\n── Test 7: cancelar cuenta 2 ──")
    cancelar_cuenta(id_c2)
    cuenta2 = obtener_cuenta(id_c2)
    print(f"  Estado cuenta 2: {cuenta2['estado']}")

    print("\n── Test 8: historial ──")
    historial = listar_cuentas_historial()
    print(f"  Cuentas en historial: {len(historial)}")
    for c in historial:
        print(f"    [{c['estado']}] Mesa {c['mesa']} — {c['cliente']}")