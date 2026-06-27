"""
modules/inventario.py — El G POS
Gestión de productos (tienda + cocina), categorías, insumos y recetas.
"""

from database import get_connection
from auth import requiere_admin


# ════════════════════════════════════════════════════════════
# CATEGORÍAS
# ════════════════════════════════════════════════════════════

def listar_categorias(tipo: str = None) -> list:
    """
    Retorna todas las categorías.
    tipo: 'tienda' | 'cocina' | None (todas)
    """
    conn = get_connection()
    if tipo:
        filas = conn.execute(
            "SELECT * FROM categorias WHERE tipo = ? ORDER BY nombre", (tipo,)
        ).fetchall()
    else:
        filas = conn.execute(
            "SELECT * FROM categorias ORDER BY tipo, nombre"
        ).fetchall()
    conn.close()
    return [dict(f) for f in filas]


@requiere_admin
def crear_categoria(nombre: str, tipo: str) -> bool:
    """Crea una categoría nueva. tipo: 'tienda' | 'cocina'."""
    if tipo not in ("tienda", "cocina"):
        raise ValueError("tipo debe ser 'tienda' o 'cocina'.")
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO categorias (nombre, tipo) VALUES (?, ?)",
            (nombre.strip(), tipo)
        )
        conn.commit()
        return True
    except Exception:
        return False  # nombre duplicado
    finally:
        conn.close()


@requiere_admin
def eliminar_categoria(categoria_id: int) -> bool:
    """Elimina una categoría si no tiene productos asociados."""
    conn = get_connection()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM productos WHERE categoria_id = ?",
            (categoria_id,)
        ).fetchone()[0]
        if count > 0:
            raise ValueError("No se puede eliminar: la categoría tiene productos asociados.")
        conn.execute("DELETE FROM categorias WHERE id = ?", (categoria_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════
# PRODUCTOS
# ════════════════════════════════════════════════════════════

def listar_productos(tipo: str = None, solo_activos: bool = True) -> list:
    """
    Retorna productos con nombre de categoría incluido.
    tipo: 'tienda' | 'cocina' | None (todos)
    """
    conn = get_connection()
    query = """
        SELECT p.*, c.nombre AS categoria_nombre, c.tipo AS categoria_tipo
        FROM productos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE 1=1
    """
    params = []
    if solo_activos:
        query += " AND p.activo = 1"
    if tipo:
        query += " AND c.tipo = ?"
        params.append(tipo)
    query += " ORDER BY c.tipo, c.nombre, p.nombre"

    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def buscar_productos(texto: str, tipo: str = None) -> list:
    """Busca productos por nombre o código (búsqueda parcial)."""
    conn = get_connection()
    query = """
        SELECT p.*, c.nombre AS categoria_nombre, c.tipo AS categoria_tipo
        FROM productos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE p.activo = 1
          AND (p.nombre LIKE ? OR p.codigo LIKE ?)
    """
    params = [f"%{texto}%", f"%{texto}%"]
    if tipo:
        query += " AND c.tipo = ?"
        params.append(tipo)
    query += " ORDER BY p.nombre"

    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def obtener_producto(producto_id: int) -> dict | None:
    """Retorna un producto por ID, o None si no existe."""
    conn = get_connection()
    fila = conn.execute("""
        SELECT p.*, c.nombre AS categoria_nombre, c.tipo AS categoria_tipo
        FROM productos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE p.id = ?
    """, (producto_id,)).fetchone()
    conn.close()
    return dict(fila) if fila else None


@requiere_admin
def crear_producto(
    nombre: str,
    categoria_id: int,
    precio_venta: float,
    precio_costo: float = 0,
    stock: float = 0,
    stock_minimo: float = 0,
    codigo: str = None
) -> int:
    """
    Crea un nuevo producto. Retorna el ID generado.
    Válido tanto para tienda como para productos terminados de cocina.
    """
    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO productos
                (nombre, codigo, precio_venta, precio_costo, stock, stock_minimo, categoria_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            nombre.strip(),
            codigo.strip() if codigo else None,
            precio_venta,
            precio_costo,
            stock,
            stock_minimo,
            categoria_id
        ))
        conn.commit()
        prod_id = cur.lastrowid
    finally:
        conn.close()

    try:
        from modules.auditoria import registrar
        registrar("inventario", f"Producto creado — {nombre.strip()} (ID {prod_id})", referencia_id=prod_id)
    except Exception:
        pass
    return prod_id


@requiere_admin
def editar_producto(producto_id: int, **campos) -> bool:
    """
    Edita uno o más campos de un producto.
    Uso: editar_producto(3, precio_venta=15000, stock_minimo=5)
    Campos permitidos: nombre, codigo, precio_venta, precio_costo,
                       stock, stock_minimo, categoria_id, activo
    """
    permitidos = {
        "nombre", "codigo", "precio_venta", "precio_costo",
        "stock", "stock_minimo", "categoria_id", "activo"
    }
    campos_validos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos_validos:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in campos_validos)
    valores    = list(campos_validos.values()) + [producto_id]

    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE productos SET {set_clause} WHERE id = ?", valores
        )
        conn.commit()
    finally:
        conn.close()

    try:
        from modules.auditoria import registrar
        campos_str = ", ".join(campos_validos.keys())
        registrar("inventario", f"Producto #{producto_id} editado — campos: {campos_str}", referencia_id=producto_id)
    except Exception:
        pass
    return True


@requiere_admin
def desactivar_producto(producto_id: int) -> bool:
    """Desactiva un producto (no lo elimina)."""
    resultado = editar_producto(producto_id, activo=0)
    if resultado:
        try:
            from modules.auditoria import registrar
            registrar("inventario", f"Producto #{producto_id} desactivado", referencia_id=producto_id)
        except Exception:
            pass
    return resultado


def actualizar_stock(producto_id: int, cantidad: float, conn=None) -> bool:
    """
    Ajusta el stock de un producto sumando 'cantidad'.
    Usa cantidad negativa para descontar (ej: al vender).
    Acepta una conexión externa para usarse dentro de transacciones.
    """
    cerrar = conn is None
    if cerrar:
        conn = get_connection()
    try:
        conn.execute(
            "UPDATE productos SET stock = stock + ? WHERE id = ?",
            (cantidad, producto_id)
        )
        if cerrar:
            conn.commit()
        return True
    finally:
        if cerrar:
            conn.close()


def productos_bajo_stock() -> list:
    """Retorna productos cuyo stock está en o por debajo del mínimo."""
    conn = get_connection()
    filas = conn.execute("""
        SELECT p.*, c.nombre AS categoria_nombre, c.tipo AS categoria_tipo
        FROM productos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE p.activo = 1
          AND p.stock <= p.stock_minimo
          AND p.stock_minimo > 0
        ORDER BY (p.stock - p.stock_minimo)
    """).fetchall()
    conn.close()
    return [dict(f) for f in filas]


# ════════════════════════════════════════════════════════════
# INSUMOS DE COCINA
# ════════════════════════════════════════════════════════════

def listar_insumos(solo_activos: bool = True) -> list:
    """Retorna todos los insumos de cocina."""
    conn = get_connection()
    query = "SELECT * FROM insumos"
    if solo_activos:
        query += " WHERE activo = 1"
    query += " ORDER BY nombre"
    filas = conn.execute(query).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def obtener_insumo(insumo_id: int) -> dict | None:
    conn = get_connection()
    fila = conn.execute(
        "SELECT * FROM insumos WHERE id = ?", (insumo_id,)
    ).fetchone()
    conn.close()
    return dict(fila) if fila else None


@requiere_admin
def crear_insumo(
    nombre: str,
    stock: float = 0,
    unidad: str = "unidad",
    stock_minimo: float = 0
) -> int:
    """Crea un insumo de cocina. Retorna el ID generado."""
    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO insumos (nombre, stock, unidad, stock_minimo)
            VALUES (?, ?, ?, ?)
        """, (nombre.strip(), stock, unidad, stock_minimo))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


@requiere_admin
def editar_insumo(insumo_id: int, **campos) -> bool:
    """Edita campos de un insumo. Campos: nombre, stock, unidad, stock_minimo, activo."""
    permitidos = {"nombre", "stock", "unidad", "stock_minimo", "activo"}
    campos_validos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos_validos:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in campos_validos)
    valores    = list(campos_validos.values()) + [insumo_id]

    conn = get_connection()
    try:
        conn.execute(f"UPDATE insumos SET {set_clause} WHERE id = ?", valores)
        conn.commit()
        return True
    finally:
        conn.close()


def actualizar_stock_insumo(insumo_id: int, cantidad: float, conn=None) -> bool:
    """
    Ajusta el stock de un insumo.
    cantidad negativa para descontar (al vender un producto que usa el insumo).
    """
    cerrar = conn is None
    if cerrar:
        conn = get_connection()
    try:
        conn.execute(
            "UPDATE insumos SET stock = stock + ? WHERE id = ?",
            (cantidad, insumo_id)
        )
        if cerrar:
            conn.commit()
        return True
    finally:
        if cerrar:
            conn.close()


def insumos_bajo_stock() -> list:
    """Retorna insumos cuyo stock está en o por debajo del mínimo."""
    conn = get_connection()
    filas = conn.execute("""
        SELECT * FROM insumos
        WHERE activo = 1
          AND stock <= stock_minimo
          AND stock_minimo > 0
        ORDER BY (stock - stock_minimo)
    """).fetchall()
    conn.close()
    return [dict(f) for f in filas]


# ════════════════════════════════════════════════════════════
# RECETAS (producto cocina ↔ insumos)
# ════════════════════════════════════════════════════════════

def obtener_receta(producto_id: int) -> list:
    """
    Retorna los insumos que componen un producto de cocina,
    con nombre y unidad de cada insumo.
    """
    conn = get_connection()
    filas = conn.execute("""
        SELECT ri.*, i.nombre AS insumo_nombre, i.unidad
        FROM receta_insumos ri
        JOIN insumos i ON ri.insumo_id = i.id
        WHERE ri.producto_id = ?
    """, (producto_id,)).fetchall()
    conn.close()
    return [dict(f) for f in filas]


@requiere_admin
def guardar_receta(producto_id: int, insumos: list[dict]) -> bool:
    """
    Reemplaza la receta completa de un producto.
    insumos: [{"insumo_id": 1, "cantidad": 2}, ...]
    """
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM receta_insumos WHERE producto_id = ?", (producto_id,)
        )
        conn.executemany("""
            INSERT INTO receta_insumos (producto_id, insumo_id, cantidad)
            VALUES (?, ?, ?)
        """, [(producto_id, i["insumo_id"], i["cantidad"]) for i in insumos])
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def descontar_insumos_por_venta(producto_id: int, cantidad_vendida: float, conn=None) -> bool:
    """
    Descuenta del stock de insumos según la receta del producto y
    la cantidad vendida. Se llama desde el módulo de ventas.
    Acepta conexión externa para ejecutarse dentro de una transacción.
    """
    receta = obtener_receta(producto_id)
    if not receta:
        return True  # producto sin receta (tienda), no hay nada que descontar

    cerrar = conn is None
    if cerrar:
        conn = get_connection()
    try:
        for item in receta:
            conn.execute(
                "UPDATE insumos SET stock = stock - ? WHERE id = ?",
                (item["cantidad"] * cantidad_vendida, item["insumo_id"])
            )
        if cerrar:
            conn.commit()
        return True
    except Exception:
        if cerrar:
            conn.rollback()
        return False
    finally:
        if cerrar:
            conn.close()


# ════════════════════════════════════════════════════════════
# UTILIDADES
# ════════════════════════════════════════════════════════════

def calcular_margen(precio_venta: float, precio_costo: float) -> float:
    """Retorna el margen de ganancia en porcentaje."""
    if precio_costo <= 0:
        return 0.0
    return round(((precio_venta - precio_costo) / precio_costo) * 100, 2)


# ════════════════════════════════════════════════════════════
# PRUEBA DIRECTA
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from database import inicializar
    from auth import iniciar_sesion

    inicializar()
    iniciar_sesion("admin", "admin123")

    print("\n── Categorías ──")
    for c in listar_categorias():
        print(f"  [{c['tipo']}] {c['nombre']}")

    print("\n── Crear productos de prueba ──")
    # producto tienda
    cat_sobres = next(c["id"] for c in listar_categorias() if "Sobres" in c["nombre"])
    id_sobre = crear_producto(
        nombre="Sobre Pokemon Scarlet & Violet",
        categoria_id=cat_sobres,
        precio_venta=15000,
        precio_costo=9000,
        stock=50,
        stock_minimo=10,
        codigo="PKM-SV-001"
    )
    print(f"  Sobre TCG creado con ID: {id_sobre}")

    # producto cocina
    cat_comida = next(c["id"] for c in listar_categorias() if "Comidas" in c["nombre"])
    id_hamburguesa = crear_producto(
        nombre="Hamburguesa clásica",
        categoria_id=cat_comida,
        precio_venta=12000,
        precio_costo=5500,
        stock=0,
        codigo="HAM-001"
    )
    print(f"  Hamburguesa creada con ID: {id_hamburguesa}")

    print("\n── Crear insumos de cocina ──")
    id_carne  = crear_insumo("Carne de res (100g)", stock=30, unidad="porción", stock_minimo=5)
    id_pan    = crear_insumo("Pan de hamburguesa",  stock=30, unidad="unidad",  stock_minimo=5)
    id_queso  = crear_insumo("Queso tajada",        stock=50, unidad="unidad",  stock_minimo=10)
    print(f"  Insumos creados: carne={id_carne}, pan={id_pan}, queso={id_queso}")

    print("\n── Guardar receta ──")
    ok = guardar_receta(id_hamburguesa, [
        {"insumo_id": id_carne, "cantidad": 1},
        {"insumo_id": id_pan,   "cantidad": 1},
        {"insumo_id": id_queso, "cantidad": 1},
    ])
    print(f"  Receta guardada: {ok}")

    receta = obtener_receta(id_hamburguesa)
    for r in receta:
        print(f"    - {r['insumo_nombre']}: {r['cantidad']} {r['unidad']}")

    print("\n── Margen de ganancia ──")
    p = obtener_producto(id_sobre)
    margen = calcular_margen(p["precio_venta"], p["precio_costo"])
    print(f"  {p['nombre']}: {margen}% de margen")

    print("\n── Descontar insumos (simula venta de 2 hamburguesas) ──")
    descontar_insumos_por_venta(id_hamburguesa, 2)
    for i in listar_insumos():
        print(f"  {i['nombre']}: stock={i['stock']}")

    print("\n── Alertas de stock bajo ──")
    actualizar_stock(id_sobre, -45)  # dejamos solo 5 (mínimo era 10)
    bajos = productos_bajo_stock()
    print(f"  Productos bajo mínimo: {len(bajos)}")
    for p in bajos:
        print(f"    - {p['nombre']}: stock={p['stock']} / mínimo={p['stock_minimo']}")
