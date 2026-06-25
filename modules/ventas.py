"""
modules/ventas.py — El G POS
Registro de ventas, manejo de carrito y coordinación con inventario.
"""

from database import get_connection
from auth import get_usuario_id, requiere_admin
from modules.clientes import obtener_cliente
from modules.inventario import (
    obtener_producto,
    actualizar_stock,
    actualizar_stock_insumo,
    descontar_insumos_por_venta,
    obtener_receta,
    obtener_insumo,
)
from datetime import datetime

IVA_POR_DEFECTO = 0.19


def _actualizar_cajas_sesion(conn, sesion_id: int, pagos: list, signo: float = 1):
    """
    Actualiza total_ventas, total_efectivo y total_digital en la sesion.
    signo=1 para ingresos (ventas), signo=-1 para egresos (pedidos).
    """
    if not sesion_id:
        return
    from modules.caja import METODOS_DIGITALES
    efectivo = sum(p["monto"] for p in pagos if p["metodo"] == "efectivo")
    digital  = sum(p["monto"] for p in pagos if p["metodo"] in METODOS_DIGITALES)
    total    = efectivo + digital
    conn.execute("""
        UPDATE sesiones_caja
        SET total_ventas   = total_ventas   + ?,
            total_efectivo = total_efectivo + ?,
            total_digital  = total_digital  + ?
        WHERE id = ?
    """, (total * signo, efectivo * signo, digital * signo, sesion_id))




# ════════════════════════════════════════════════════════════
# CARRITO (estado en memoria durante una venta activa)
# ════════════════════════════════════════════════════════════

class Carrito:
    """
    Maneja los ítems de una venta antes de confirmarla.
    Cada ítem es un dict con:
        tipo        : 'producto' | 'combo'
        id          : producto_id o combo_id
        nombre      : str
        precio_unit : float
        cantidad    : float
        subtotal    : float
        venta_tipo  : 'tienda' | 'cocina'
    """

    def __init__(self):
        self._items: list[dict] = []

    # ── Agregar ───────────────────────────────────────────────────────────────
    def agregar_producto(self, producto_id: int, cantidad: float = 1) -> dict:
        """
        Agrega un producto al carrito o incrementa su cantidad si ya existe.
        Retorna el ítem actualizado.
        """
        producto = obtener_producto(producto_id)
        if not producto:
            raise ValueError(f"Producto ID {producto_id} no encontrado.")
        if not producto["activo"]:
            raise ValueError(f"El producto '{producto['nombre']}' no está activo.")

        # Tienda: valida stock directo. Cocina: valida insumos disponibles.
        if producto["categoria_tipo"] == "tienda":
            if producto["stock"] < cantidad:
                raise ValueError(
                    f"Stock insuficiente para '{producto['nombre']}'. "
                    f"Disponible: {producto['stock']}"
                )
        else:
            receta = obtener_receta(producto_id)
            for r in receta:
                insumo = obtener_insumo(r["insumo_id"])
                if insumo and insumo["stock"] < r["cantidad"] * cantidad:
                    raise ValueError(
                        f"Insumo insuficiente: '{insumo['nombre']}'. "
                        f"Disponible: {insumo['stock']} {insumo['unidad']}, "
                        f"requerido: {r['cantidad'] * cantidad}"
                    )

        # ¿Ya está en el carrito?
        for item in self._items:
            if item["tipo"] == "producto" and item["id"] == producto_id:
                item["cantidad"]  += cantidad
                item["subtotal"]   = item["cantidad"] * item["precio_unit"]
                return item

        item = {
            "tipo":        "producto",
            "id":          producto_id,
            "nombre":      producto["nombre"],
            "precio_unit": producto["precio_venta"],
            "cantidad":    cantidad,
            "subtotal":    producto["precio_venta"] * cantidad,
            "venta_tipo":  producto["categoria_tipo"],
        }
        self._items.append(item)
        return item

    def agregar_combo(self, combo_id: int, cantidad: float = 1) -> dict:
        """Agrega un combo al carrito validando stock e insumos de sus componentes."""
        conn = get_connection()
        combo = conn.execute(
            "SELECT * FROM combos WHERE id = ? AND activo = 1", (combo_id,)
        ).fetchone()
        if not combo:
            conn.close()
            raise ValueError(f"Combo ID {combo_id} no encontrado o inactivo.")
        combo = dict(combo)

        combo_prods = conn.execute("""
            SELECT cp.producto_id, cp.cantidad, p.nombre, p.stock,
                   c.tipo AS categoria_tipo
            FROM combo_productos cp
            JOIN productos p  ON cp.producto_id = p.id
            JOIN categorias c ON p.categoria_id = c.id
            WHERE cp.combo_id = ?
        """, (combo_id,)).fetchall()
        conn.close()

        for cp in combo_prods:
            needed = cp["cantidad"] * cantidad
            if cp["categoria_tipo"] == "tienda":
                if cp["stock"] < needed:
                    raise ValueError(
                        f"Stock insuficiente para '{cp['nombre']}' en el combo. "
                        f"Disponible: {cp['stock']}"
                    )
            else:
                receta = obtener_receta(cp["producto_id"])
                for r in receta:
                    insumo = obtener_insumo(r["insumo_id"])
                    if insumo and insumo["stock"] < r["cantidad"] * needed:
                        raise ValueError(
                            f"Insumo insuficiente: '{insumo['nombre']}'. "
                            f"Disponible: {insumo['stock']} {insumo['unidad']}"
                        )

        for item in self._items:
            if item["tipo"] == "combo" and item["id"] == combo_id:
                item["cantidad"] += cantidad
                item["subtotal"]  = item["cantidad"] * item["precio_unit"]
                return item

        item = {
            "tipo":        "combo",
            "id":          combo_id,
            "nombre":      combo["nombre"],
            "precio_unit": combo["precio"],
            "cantidad":    cantidad,
            "subtotal":    combo["precio"] * cantidad,
            "venta_tipo":  "cocina",
        }
        self._items.append(item)
        return item

    # ── Modificar / quitar ────────────────────────────────────────────────────
    def cambiar_cantidad(self, index: int, nueva_cantidad: float):
        """Cambia la cantidad de un ítem por su posición en la lista."""
        if index < 0 or index >= len(self._items):
            raise IndexError("Índice de ítem inválido.")
        if nueva_cantidad <= 0:
            self.quitar_item(index)
            return
        self._items[index]["cantidad"] = nueva_cantidad
        self._items[index]["subtotal"] = nueva_cantidad * self._items[index]["precio_unit"]

    def quitar_item(self, index: int):
        """Elimina un ítem del carrito por posición."""
        if 0 <= index < len(self._items):
            self._items.pop(index)

    def limpiar(self):
        """Vacía el carrito completamente."""
        self._items.clear()

    # ── Consultas ─────────────────────────────────────────────────────────────
    def get_items(self) -> list[dict]:
        return list(self._items)

    def total(self) -> float:
        return round(sum(i["subtotal"] for i in self._items), 2)

    def cantidad_items(self) -> int:
        return len(self._items)

    def esta_vacio(self) -> bool:
        return len(self._items) == 0

    def determinar_tipo_venta(self) -> str:
        """
        Determina el tipo general de la venta:
        - 'tienda'  : todos los ítems son de tienda
        - 'cocina'  : todos los ítems son de cocina
        - 'mixta'   : combina ambos (registrada como 'tienda' por defecto)
        """
        tipos = {i["venta_tipo"] for i in self._items}
        if tipos == {"tienda"}:
            return "tienda"
        if tipos == {"cocina"}:
            return "cocina"
        return "tienda"  # mixta → se registra como tienda


# ════════════════════════════════════════════════════════════
# REGISTRO DE VENTA
# ════════════════════════════════════════════════════════════

def registrar_venta(
    carrito: Carrito,
    metodo_pago: str = "efectivo",
    descuento: float = 0,
    sesion_id: int = None,
    cliente_id: int = None,
    emitir_factura: bool = False,
    iva_porcentaje: float = IVA_POR_DEFECTO,
    notas: str = None,
    pagos: list[dict] = None
) -> int:
    """
    Confirma la venta, persiste todo en la base de datos y
    descuenta stock de productos e insumos en una sola transacción.

    pagos: lista para pago mixto, ej:
        [{"metodo": "efectivo", "monto": 10000},
         {"metodo": "nequi",    "monto": 5000}]
    Si se omite, se usa metodo_pago como único método por el total.
    Si cliente_id se proporciona o emitir_factura=True, se genera una factura.
    Retorna el ID de la venta generada.
    """
    if carrito.esta_vacio():
        raise ValueError("El carrito está vacío.")

    METODOS = {"efectivo", "transferencia", "tarjeta", "nequi", "daviplata"}

    # — Resolver método y pagos —
    total = max(0, carrito.total() - descuento)

    if pagos:
        # Validar métodos
        for p in pagos:
            if p["metodo"] not in METODOS:
                raise ValueError(f"Método de pago inválido: {p['metodo']}")
        suma_pagos = sum(p["monto"] for p in pagos)
        if round(suma_pagos, 2) < round(total, 2):
            raise ValueError(
                f"Los pagos suman {suma_pagos:,.0f} pero el total es {total:,.0f}."
            )
        metodo_final = "mixto" if len(pagos) > 1 else pagos[0]["metodo"]
    else:
        if metodo_pago not in METODOS:
            raise ValueError(f"Método de pago inválido: {metodo_pago}")
        metodo_final = metodo_pago
        pagos = [{"metodo": metodo_pago, "monto": total}]

    tipo_venta   = carrito.determinar_tipo_venta()
    usuario_id   = get_usuario_id()
    items        = carrito.get_items()

    conn = get_connection()
    try:
        # 1. Insertar cabecera de venta
        from datetime import datetime
        fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute("""
            INSERT INTO ventas
                (fecha, total, descuento, metodo_pago, tipo, usuario_id, sesion_id, cliente_id, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fecha_ahora, total, descuento, metodo_final, tipo_venta, usuario_id, sesion_id, cliente_id, notas))

        venta_id = cur.lastrowid

        # 2. Insertar detalles y descontar stock
        for item in items:
            # Detalle de venta
            conn.execute("""
                INSERT INTO detalle_venta
                    (venta_id, producto_id, combo_id, cantidad, precio_unit, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                venta_id,
                item["id"]   if item["tipo"] == "producto" else None,
                item["id"]   if item["tipo"] == "combo"    else None,
                item["cantidad"],
                item["precio_unit"],
                item["subtotal"],
            ))

            # Re-validar y descontar stock dentro de la transacción
            if item["tipo"] == "producto":
                producto = obtener_producto(item["id"])
                if producto["categoria_tipo"] == "tienda":
                    fila = conn.execute(
                        "SELECT stock FROM productos WHERE id = ?", (item["id"],)
                    ).fetchone()
                    if fila["stock"] < item["cantidad"]:
                        raise ValueError(
                            f"Stock insuficiente para '{producto['nombre']}'. "
                            f"Disponible: {fila['stock']}"
                        )
                    actualizar_stock(item["id"], -item["cantidad"], conn=conn)
                else:
                    receta = obtener_receta(item["id"])
                    for r in receta:
                        fila = conn.execute(
                            "SELECT stock, nombre FROM insumos WHERE id = ?",
                            (r["insumo_id"],)
                        ).fetchone()
                        needed = r["cantidad"] * item["cantidad"]
                        if fila["stock"] < needed:
                            raise ValueError(
                                f"Insumo insuficiente: '{fila['nombre']}'. "
                                f"Disponible: {fila['stock']}, necesario: {needed}"
                            )
                    descontar_insumos_por_venta(item["id"], item["cantidad"], conn=conn)

            elif item["tipo"] == "combo":
                combo_prods = _obtener_productos_combo(item["id"], conn)
                for cp in combo_prods:
                    producto = obtener_producto(cp["producto_id"])
                    if producto["categoria_tipo"] == "tienda":
                        fila = conn.execute(
                            "SELECT stock FROM productos WHERE id = ?", (cp["producto_id"],)
                        ).fetchone()
                        needed = cp["cantidad"] * item["cantidad"]
                        if fila["stock"] < needed:
                            raise ValueError(
                                f"Stock insuficiente para '{producto['nombre']}' en combo. "
                                f"Disponible: {fila['stock']}"
                            )
                        actualizar_stock(
                            cp["producto_id"],
                            -(cp["cantidad"] * item["cantidad"]),
                            conn=conn
                        )
                    else:
                        receta = obtener_receta(cp["producto_id"])
                        for r in receta:
                            fila = conn.execute(
                                "SELECT stock, nombre FROM insumos WHERE id = ?",
                                (r["insumo_id"],)
                            ).fetchone()
                            needed = r["cantidad"] * cp["cantidad"] * item["cantidad"]
                            if fila["stock"] < needed:
                                raise ValueError(
                                    f"Insumo insuficiente: '{fila['nombre']}'. "
                                    f"Disponible: {fila['stock']}"
                                )
                        descontar_insumos_por_venta(
                            cp["producto_id"],
                            cp["cantidad"] * item["cantidad"],
                            conn=conn
                        )

        # 3. Actualizar total acumulado por caja
        if sesion_id:
            _actualizar_cajas_sesion(conn, sesion_id, pagos, signo=1)

        # 3b. Insertar detalle de pagos
        for pago in pagos:
            conn.execute("""
                INSERT INTO pagos_venta (venta_id, metodo, monto)
                VALUES (?, ?, ?)
            """, (venta_id, pago["metodo"], pago["monto"]))

        # 3c. Generar factura si aplica
        if emitir_factura or cliente_id:
            _crear_factura(conn, venta_id, cliente_id, total, iva_porcentaje, notas)

        conn.commit()
        carrito.limpiar()
        return venta_id

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _generar_numero_factura(conn) -> str:
    """Genera un número de factura único basado en la fecha."""
    prefijo = datetime.now().strftime("%Y%m%d")
    fila = conn.execute(
        "SELECT COUNT(*) FROM facturas WHERE numero LIKE ?",
        (f"{prefijo}%",)
    ).fetchone()
    secuencia = (fila[0] or 0) + 1
    return f"F{prefijo}-{secuencia:04d}"


def _crear_factura(
    conn,
    venta_id: int,
    cliente_id: int | None,
    total: float,
    iva_porcentaje: float,
    notas: str | None = None
) -> int:
    """Crea la factura asociada a una venta."""
    cliente = None
    if cliente_id:
        cliente = obtener_cliente(cliente_id)

    if cliente:
        tipo_documento = cliente["tipo_documento"]
        documento = cliente["documento"]
        direccion = cliente["direccion"]
        telefono = cliente["telefono"]
        email = cliente["email"]
    else:
        tipo_documento = "CONSUMIDOR_FINAL"
        documento = ""
        direccion = ""
        telefono = ""
        email = ""

    total_base = round(total / (1 + iva_porcentaje), 2) if iva_porcentaje else total
    iva = round(total - total_base, 2) if iva_porcentaje else 0.0

    numero = _generar_numero_factura(conn)
    cur = conn.execute(
        """
        INSERT INTO facturas
            (venta_id, cliente_id, numero, tipo_documento, documento,
             direccion, telefono, email, fecha, total_base,
             iva_porcentaje, iva, total, notas)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'), ?, ?, ?, ?, ?)
        """,
        (
            venta_id,
            cliente_id,
            numero,
            tipo_documento,
            documento,
            direccion,
            telefono,
            email,
            total_base,
            iva_porcentaje,
            iva,
            total,
            notas,
        )
    )
    return cur.lastrowid


def _obtener_productos_combo(combo_id: int, conn) -> list:
    """Retorna los productos que componen un combo (uso interno)."""
    filas = conn.execute(
        "SELECT producto_id, cantidad FROM combo_productos WHERE combo_id = ?",
        (combo_id,)
    ).fetchall()
    return [dict(f) for f in filas]


# ════════════════════════════════════════════════════════════
# CONSULTAS DE VENTAS
# ════════════════════════════════════════════════════════════

def obtener_venta(venta_id: int) -> dict | None:
    """Retorna una venta con su detalle completo."""
    conn = get_connection()
    venta = conn.execute("""
        SELECT v.*, u.usuario AS vendedor
        FROM ventas v
        JOIN usuarios u ON v.usuario_id = u.id
        WHERE v.id = ?
    """, (venta_id,)).fetchone()

    if not venta:
        conn.close()
        return None

    detalle = conn.execute("""
        SELECT
            dv.*,
            COALESCE(p.nombre, c.nombre) AS nombre_item
        FROM detalle_venta dv
        LEFT JOIN productos p ON dv.producto_id = p.id
        LEFT JOIN combos    c ON dv.combo_id    = c.id
        WHERE dv.venta_id = ?
    """, (venta_id,)).fetchall()

    conn.close()
    return {**dict(venta), "detalle": [dict(d) for d in detalle]}


def listar_ventas(
    fecha_inicio: str = None,
    fecha_fin: str    = None,
    tipo: str         = None,
    usuario_id: int   = None,
    limite: int       = 100
) -> list:
    """
    Lista ventas con filtros opcionales.
    Fechas en formato 'YYYY-MM-DD'.
    """
    conn  = get_connection()
    query = """
        SELECT v.*, u.usuario AS vendedor
        FROM ventas v
        JOIN usuarios u ON v.usuario_id = u.id
        WHERE 1=1
    """
    params = []

    if fecha_inicio:
        query += " AND date(v.fecha) >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND date(v.fecha) <= ?"
        params.append(fecha_fin)
    if tipo:
        query += " AND v.tipo = ?"
        params.append(tipo)
    if usuario_id:
        query += " AND v.usuario_id = ?"
        params.append(usuario_id)

    query += " ORDER BY v.fecha DESC LIMIT ?"
    params.append(limite)

    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def ventas_del_dia(tipo: str = None) -> list:
    """Retorna todas las ventas del día actual."""
    from datetime import date
    hoy = date.today().isoformat()
    return listar_ventas(fecha_inicio=hoy, fecha_fin=hoy, tipo=tipo)


def resumen_del_dia() -> dict:
    """
    Retorna un resumen de las ventas del día:
    total general, por tipo y por método de pago.
    """
    ventas = ventas_del_dia()
    resumen = {
        "total":         sum(v["total"] for v in ventas),
        "num_ventas":    len(ventas),
        "por_tipo": {
            "tienda": sum(v["total"] for v in ventas if v["tipo"] == "tienda"),
            "cocina": sum(v["total"] for v in ventas if v["tipo"] == "cocina"),
        },
        "por_metodo": {},
    }
    for v in ventas:
        m = v["metodo_pago"]
        resumen["por_metodo"][m] = resumen["por_metodo"].get(m, 0) + v["total"]

    return resumen


@requiere_admin
def anular_venta(venta_id: int) -> bool:
    """
    Elimina una venta y revierte el stock de productos e insumos. Solo admin.
    """
    conn = get_connection()
    try:
        detalle = conn.execute(
            "SELECT * FROM detalle_venta WHERE venta_id = ?", (venta_id,)
        ).fetchall()

        for item in detalle:
            cantidad = item["cantidad"]

            if item["producto_id"]:
                producto = obtener_producto(item["producto_id"])
                if producto:
                    if producto["categoria_tipo"] == "tienda":
                        actualizar_stock(item["producto_id"], cantidad, conn=conn)
                    else:
                        for r in obtener_receta(item["producto_id"]):
                            actualizar_stock_insumo(
                                r["insumo_id"], r["cantidad"] * cantidad, conn=conn
                            )

            elif item["combo_id"]:
                for cp in _obtener_productos_combo(item["combo_id"], conn):
                    producto = obtener_producto(cp["producto_id"])
                    if producto:
                        if producto["categoria_tipo"] == "tienda":
                            actualizar_stock(
                                cp["producto_id"], cp["cantidad"] * cantidad, conn=conn
                            )
                        else:
                            for r in obtener_receta(cp["producto_id"]):
                                actualizar_stock_insumo(
                                    r["insumo_id"],
                                    r["cantidad"] * cp["cantidad"] * cantidad,
                                    conn=conn
                                )

        conn.execute("DELETE FROM ventas WHERE id = ?", (venta_id,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════
# COMBOS — gestión
# ════════════════════════════════════════════════════════════

def listar_combos(solo_activos: bool = True) -> list:
    """Retorna todos los combos con sus productos."""
    conn = get_connection()
    query = "SELECT * FROM combos"
    if solo_activos:
        query += " WHERE activo = 1"
    query += " ORDER BY nombre"
    combos = [dict(f) for f in conn.execute(query).fetchall()]

    for combo in combos:
        combo["productos"] = [dict(f) for f in conn.execute("""
            SELECT cp.cantidad, p.nombre, p.precio_venta
            FROM combo_productos cp
            JOIN productos p ON cp.producto_id = p.id
            WHERE cp.combo_id = ?
        """, (combo["id"],)).fetchall()]

    conn.close()
    return combos


@requiere_admin
def crear_combo(nombre: str, precio: float, productos: list[dict], descripcion: str = None) -> int:
    """
    Crea un combo con sus productos.
    productos: [{"producto_id": 1, "cantidad": 1}, ...]
    Retorna el ID generado.
    """
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO combos (nombre, precio, descripcion) VALUES (?, ?, ?)",
            (nombre.strip(), precio, descripcion)
        )
        combo_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO combo_productos (combo_id, producto_id, cantidad) VALUES (?, ?, ?)",
            [(combo_id, p["producto_id"], p["cantidad"]) for p in productos]
        )
        conn.commit()
        return combo_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@requiere_admin
def editar_combo(combo_id: int, **campos) -> bool:
    """Edita nombre, precio, descripcion o activo de un combo."""
    permitidos = {"nombre", "precio", "descripcion", "activo"}
    campos_validos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos_validos:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in campos_validos)
    valores    = list(campos_validos.values()) + [combo_id]

    conn = get_connection()
    try:
        conn.execute(f"UPDATE combos SET {set_clause} WHERE id = ?", valores)
        conn.commit()
        return True
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════
# PRUEBA DIRECTA
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from database import inicializar
    from auth import iniciar_sesion
    from modules.inventario import crear_producto, crear_insumo, guardar_receta, listar_categorias

    inicializar()
    iniciar_sesion("admin", "admin123")

    # Preparar datos mínimos
    cats    = {c["nombre"]: c["id"] for c in listar_categorias()}
    id_sobre = crear_producto("Sobre TCG Test", cats["TCG - Sobres"],
                               precio_venta=15000, precio_costo=9000, stock=20)
    id_gaseosa = crear_producto("Gaseosa lata", cats["Bebidas"],
                                 precio_venta=3000, precio_costo=1500, stock=0)
    id_ham   = crear_producto("Hamburguesa test", cats["Comidas rápidas"],
                               precio_venta=12000, precio_costo=5500, stock=0)

    id_carne = crear_insumo("Carne test", stock=20, unidad="porción")
    id_pan   = crear_insumo("Pan test",   stock=20, unidad="unidad")
    guardar_receta(id_ham, [
        {"insumo_id": id_carne, "cantidad": 1},
        {"insumo_id": id_pan,   "cantidad": 1},
    ])

    # Crear combo: hamburguesa + gaseosa
    id_combo = crear_combo(
        "Combo 1 — Hamburguesa + Gaseosa",
        precio=13500,
        productos=[
            {"producto_id": id_ham,     "cantidad": 1},
            {"producto_id": id_gaseosa, "cantidad": 1},
        ]
    )

    print("\n── Test 1: venta de tienda ──")
    carrito = Carrito()
    carrito.agregar_producto(id_sobre, 2)
    print(f"  Ítems: {carrito.cantidad_items()} | Total: ${carrito.total():,.0f}")
    venta_id = registrar_venta(carrito, metodo_pago="efectivo")
    print(f"  Venta registrada ID: {venta_id}")
    venta = obtener_venta(venta_id)
    print(f"  Total guardado: ${venta['total']:,.0f} | Tipo: {venta['tipo']}")

    print("\n── Test 2: venta de combo ──")
    carrito2 = Carrito()
    carrito2.agregar_combo(id_combo, 1)
    print(f"  Ítems: {carrito2.cantidad_items()} | Total: ${carrito2.total():,.0f}")
    venta_id2 = registrar_venta(carrito2, metodo_pago="nequi")
    print(f"  Venta registrada ID: {venta_id2}")

    print("\n── Test 3: resumen del día ──")
    resumen = resumen_del_dia()
    print(f"  Total del día:  ${resumen['total']:,.0f}")
    print(f"  Ventas tienda:  ${resumen['por_tipo']['tienda']:,.0f}")
    print(f"  Ventas cocina:  ${resumen['por_tipo']['cocina']:,.0f}")
    print(f"  Métodos de pago: {resumen['por_metodo']}")

    print("\n── Test 4: stock insuficiente ──")
    try:
        carrito3 = Carrito()
        carrito3.agregar_producto(id_sobre, 9999)
    except ValueError as e:
        print(f"  Error esperado: {e}")