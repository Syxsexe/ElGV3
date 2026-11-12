"""
pos_api/servicios/catalogo.py — Lo que se vende y lo que se cocina.

Un artículo se crea junto con su fila de subtipo (producto, combo, adicional
o servicio) en la misma transacción: la base exige el par al confirmar. Los
costos de platos y preparaciones los recalcula la base al cambiar recetas o
costos de insumos; aquí solo se guardan las recetas.

Permisos: combos.editar para combos, preparaciones.editar para recetas de
preparaciones, inventario.editar para todo lo demás.
"""
from decimal import Decimal

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado, SinPermiso
from pos_api.seguridad import Usuario
from pos_api.servicios import combos
from pos_api.servicios.comun import actualizar, condicion_busqueda, literal_like

PERMISO_INVENTARIO = "inventario.editar"
PERMISO_COMBOS = "combos.editar"
PERMISO_PREPARACIONES = "preparaciones.editar"

TABLA_SUBTIPO = {"producto": "productos", "combo": "combos", "adicional": "adicionales", "servicio": "servicios"}
CAMPOS_ARTICULO = {"nombre", "categoria_id", "impuesto_id", "precio_venta", "activo"}
CAMPOS_SUBTIPO = {
    "producto": {"codigo", "precio_costo", "stock_minimo"},
    "combo": {"descripcion"},
    "adicional": {"insumo_id", "cantidad"},
    "servicio": set(),
}
NOMBRE_TIPO = {"producto": "producto", "combo": "combo", "adicional": "adicional", "servicio": "servicio"}


BUSCAR_NOMBRE = condicion_busqueda("nombre")


def _exigir_permiso_tipo(actor: Usuario, tipo: str) -> None:
    permiso = PERMISO_COMBOS if tipo == "combo" else PERMISO_INVENTARIO
    if not actor.puede(permiso):
        raise SinPermiso("No tienes permiso para editar este tipo de artículo.")


def _sin_duplicados(lineas: list[dict], clave: str, que: str) -> None:
    ids = [l[clave] for l in lineas]
    if len(ids) != len(set(ids)):
        raise ErrorNegocio(f"{que} tiene un componente repetido: junta las cantidades en una sola línea.")


# ── Categorías, impuestos y unidades ────────────────────────────────────────

def listar_categorias(conn) -> list[dict]:
    return conn.execute(
        """SELECT c.id, c.nombre, c.tipo, count(a.id) AS articulos
             FROM categorias c LEFT JOIN articulos a ON a.categoria_id = c.id
            GROUP BY c.id ORDER BY c.tipo DESC, c.nombre"""
    ).fetchall()


def crear_categoria(conn, actor: Usuario, nombre: str, tipo: str) -> dict:
    fila = conn.execute("INSERT INTO categorias (nombre, tipo) VALUES (%s, %s) RETURNING *", (nombre, tipo)).fetchone()
    auditar(conn, actor.id, "inventario", f"Creó la categoría {nombre} ({tipo})", "categorias", fila["id"])
    return fila


def editar_categoria(conn, actor: Usuario, categoria_id, cambios: dict) -> dict:
    fila = actualizar(conn, "categorias", categoria_id, cambios, no_existe="La categoría no existe.")
    auditar(conn, actor.id, "inventario", f"Editó la categoría {fila['nombre']}", "categorias", categoria_id)
    return fila


def borrar_categoria(conn, actor: Usuario, categoria_id) -> None:
    fila = conn.execute("DELETE FROM categorias WHERE id = %s RETURNING nombre", (categoria_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("La categoría no existe.")
    auditar(conn, actor.id, "inventario", f"Borró la categoría {fila['nombre']}", "categorias", categoria_id)


def listar_impuestos(conn) -> list[dict]:
    return conn.execute("SELECT id, codigo, nombre, tributo, tarifa FROM impuestos ORDER BY tributo DESC, tarifa DESC").fetchall()


def listar_unidades(conn) -> list[dict]:
    return conn.execute("SELECT id, simbolo, nombre FROM unidades_medida ORDER BY nombre").fetchall()


def _impuesto_por_defecto(conn, tipo: str, categoria_id) -> object:
    """Combos → INC 8; si no, según la categoría: tienda → IVA 19, cocina → INC 8."""
    fila = conn.execute(
        """SELECT i.id FROM impuestos i, categorias c
            WHERE c.id = %s
              AND i.codigo = CASE WHEN %s = 'combo' OR c.tipo = 'cocina' THEN 'INC8' ELSE 'IVA19' END""",
        (categoria_id, tipo),
    ).fetchone()
    if fila is None:
        raise NoEncontrado("La categoría no existe.")
    return fila["id"]


# ── Artículos ───────────────────────────────────────────────────────────────

def listar_articulos(conn, *, tipo=None, texto=None, categoria_id=None, solo_activos=False,
                     categoria_tipo=None) -> list[dict]:
    return conn.execute(
        """SELECT * FROM v_articulos
            WHERE (%(tipo)s::text IS NULL OR tipo = %(tipo)s)
              AND (%(categoria)s::uuid IS NULL OR categoria_id = %(categoria)s)
              AND (%(categoria_tipo)s::text IS NULL OR categoria_tipo = %(categoria_tipo)s)
              AND (NOT %(solo_activos)s OR activo)
              AND (%(patron)s::text IS NULL OR """ + BUSCAR_NOMBRE + """ OR codigo = %(texto)s)
            ORDER BY activo DESC, nombre""",
        {"tipo": tipo, "categoria": categoria_id, "solo_activos": solo_activos, "categoria_tipo": categoria_tipo,
         "patron": literal_like(texto), "texto": (texto or "").strip()},
    ).fetchall()


def vendibles(conn, texto: str | None = None, tipo: str | None = None, limite: int = 60,
              categoria_tipo: str | None = None) -> list[dict]:
    """Artículos activos para vender o consultar precio (sin costos).
    categoria_tipo: "tienda" o "cocina" (las pestañas de la venta)."""
    return conn.execute(
        """SELECT id, tipo, nombre, precio_venta, categoria_id, categoria, categoria_tipo,
                  impuesto, codigo, stock, stock_minimo, alcanza, tiene_grupos, bloqueo
             FROM v_articulos
            WHERE activo
              AND (%(tipo)s::text IS NULL OR tipo = %(tipo)s)
              AND (%(categoria_tipo)s::text IS NULL OR categoria_tipo = %(categoria_tipo)s)
              AND (%(patron)s::text IS NULL OR """ + BUSCAR_NOMBRE + """ OR codigo = %(texto)s)
            ORDER BY nombre
            LIMIT %(limite)s""",
        {"tipo": tipo, "categoria_tipo": categoria_tipo, "patron": literal_like(texto),
         "texto": (texto or "").strip(), "limite": limite},
    ).fetchall()


def obtener_articulo(conn, articulo_id) -> dict:
    fila = conn.execute("SELECT * FROM v_articulos WHERE id = %s", (articulo_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("El artículo no existe.")
    if fila["tipo"] == "combo":
        fila["productos"] = conn.execute(
            """SELECT cp.producto_id, a.nombre, cp.cantidad, p.precio_costo AS costo_unit, a.activo,
                      p.stock, c.tipo AS categoria_tipo, unidades_disponibles(cp.producto_id) AS disponibles
                 FROM combo_productos cp
                 JOIN articulos a ON a.id = cp.producto_id
                 JOIN productos p ON p.articulo_id = cp.producto_id
                 JOIN categorias c ON c.id = a.categoria_id
                WHERE cp.combo_id = %s ORDER BY a.nombre""",
            (articulo_id,),
        ).fetchall()
        fila["grupos"] = combos.grupos(conn, articulo_id)
    if fila["tipo"] == "producto":
        # Receta: insumos (o preparaciones) y productos de tienda, cada uno con
        # su costo unitario, su subtotal y su stock (para ver qué limita el plato).
        fila["receta"] = conn.execute(
            """SELECT r.insumo_id, NULL::uuid AS producto_id, i.nombre, i.unidad, r.cantidad, i.costo AS costo_unit,
                      round(r.cantidad * i.costo, 2) AS subtotal, i.stock
                 FROM receta_insumos r JOIN v_insumos i ON i.id = r.insumo_id
                WHERE r.producto_id = %(id)s
               UNION ALL
               SELECT NULL, r.producto_id, a.nombre, 'und', r.cantidad, p.precio_costo,
                      round(r.cantidad * p.precio_costo, 2), p.stock
                 FROM receta_productos r JOIN productos p ON p.articulo_id = r.producto_id
                 JOIN articulos a ON a.id = r.producto_id
                WHERE r.plato_id = %(id)s
                ORDER BY nombre""",
            {"id": articulo_id},
        ).fetchall()
    return fila


def opciones_para_vender(conn, articulo_id) -> dict:
    """Un combo activo con sus grupos y las opciones activas de cada uno, para
    elegir al venderlo. Sin costos: lo ve cualquier usuario con sesión."""
    combo = conn.execute(
        """SELECT id, nombre, precio_venta, activo, bloqueo FROM v_articulos WHERE id = %s AND tipo = 'combo'""",
        (articulo_id,),
    ).fetchone()
    if combo is None:
        raise NoEncontrado("El combo no existe.")
    if not combo["activo"]:
        raise ErrorNegocio(f"{combo['nombre']} ya no se vende.")
    if combo["bloqueo"]:
        raise ErrorNegocio(f"{combo['nombre']} no se puede vender: {combo['bloqueo']}.")
    combo["grupos"] = [
        {**g, "opciones": [{k: o[k] for k in ("producto_id", "nombre", "recargo", "categoria_tipo", "disponibles")}
                           for o in g["opciones"]]}
        for g in combos.grupos(conn, articulo_id, solo_activas=True)
    ]
    return combo


def _guardar_productos_combo(conn, combo_id, productos: list[dict]) -> None:
    _sin_duplicados(productos, "producto_id", "El combo")
    conn.execute("DELETE FROM combo_productos WHERE combo_id = %s", (combo_id,))
    if productos:
        conn.execute(
            """INSERT INTO combo_productos (combo_id, producto_id, cantidad)
               SELECT %s, x.producto_id, x.cantidad
                 FROM unnest(%s::uuid[], %s::numeric[]) AS x(producto_id, cantidad)""",
            (combo_id, [p["producto_id"] for p in productos], [p["cantidad"] for p in productos]),
        )


def _validar_grupos(grupos: list[dict]) -> None:
    nombres = [g["nombre"].strip().lower() for g in grupos]
    if len(nombres) != len(set(nombres)):
        raise ErrorNegocio("Dos grupos del combo se llaman igual: cada grupo necesita su propio nombre.")
    for g in grupos:
        if not g["opciones"]:
            raise ErrorNegocio(f"El grupo {g['nombre']} necesita al menos una opción.")
        _sin_duplicados(g["opciones"], "producto_id", f"El grupo {g['nombre']}")


def _grupos_actuales(conn, combo_id) -> list:
    """Los grupos guardados, en la misma forma que llegan, para saber si cambiaron."""
    return [(g["nombre"], g["cantidad"], {o["producto_id"]: o["recargo"] for o in g["opciones"]})
            for g in combos.grupos(conn, combo_id)]


def _grupos_pedidos(grupos: list[dict]) -> list:
    return [(g["nombre"], Decimal(g["cantidad"]), {o["producto_id"]: Decimal(o["recargo"]) for o in g["opciones"]})
            for g in grupos]


def _guardar_grupos_combo(conn, combo_id, grupos: list[dict]) -> None:
    """Reemplaza los grupos. Lo ya vendido no cambia: guarda su propia foto."""
    _validar_grupos(grupos)
    conn.execute("DELETE FROM combo_grupos WHERE combo_id = %s", (combo_id,))
    for orden, g in enumerate(grupos):
        grupo_id = conn.execute(
            "INSERT INTO combo_grupos (combo_id, nombre, cantidad, orden) VALUES (%s, %s, %s, %s) RETURNING id",
            (combo_id, g["nombre"], g["cantidad"], orden),
        ).fetchone()["id"]
        conn.execute(
            """INSERT INTO combo_opciones (grupo_id, producto_id, recargo)
               SELECT %s, x.producto_id, x.recargo FROM unnest(%s::uuid[], %s::numeric[]) AS x(producto_id, recargo)""",
            (grupo_id, [o["producto_id"] for o in g["opciones"]], [Decimal(o["recargo"]) for o in g["opciones"]]),
        )


def _exigir_contenido_combo(conn, combo_id) -> None:
    lleva = conn.execute(
        """SELECT EXISTS (SELECT 1 FROM combo_productos WHERE combo_id = %(c)s)
               OR EXISTS (SELECT 1 FROM combo_grupos WHERE combo_id = %(c)s) AS algo""",
        {"c": combo_id},
    ).fetchone()["algo"]
    if not lleva:
        raise ErrorNegocio("Un combo necesita al menos un producto fijo o un grupo para elegir.")


def _clave_receta(linea: dict) -> tuple:
    return ("insumo", linea["insumo_id"]) if linea.get("insumo_id") else ("producto", linea["producto_id"])


def _receta_sin_duplicados(receta: list[dict]) -> None:
    claves = [_clave_receta(r) for r in receta]
    if len(claves) != len(set(claves)):
        raise ErrorNegocio("La receta tiene un componente repetido: junta las cantidades en una sola línea.")


def _receta_actual(conn, producto_id) -> dict:
    """{(clase, id): cantidad} de la receta guardada, para saber si cambió."""
    return {(r["clase"], r["id"]): r["cantidad"] for r in conn.execute(
        """SELECT 'insumo' AS clase, insumo_id AS id, cantidad FROM receta_insumos WHERE producto_id = %(p)s
           UNION ALL
           SELECT 'producto', producto_id, cantidad FROM receta_productos WHERE plato_id = %(p)s""",
        {"p": producto_id})}


def _guardar_receta(conn, producto_id, receta: list[dict]) -> None:
    """Reemplaza la receta del plato: líneas de insumo (insumo_id) o de
    producto de tienda (producto_id). Vacía = sin receta (conserva su último
    costo, que pasa a editarse a mano). La base recalcula el costo."""
    _receta_sin_duplicados(receta)
    insumos = [r for r in receta if r.get("insumo_id")]
    productos = [r for r in receta if not r.get("insumo_id")]
    if any(r["producto_id"] == producto_id for r in productos):
        raise ErrorNegocio("Un plato no puede llevarse a sí mismo en la receta.")
    conn.execute("DELETE FROM receta_insumos WHERE producto_id = %s", (producto_id,))
    conn.execute("DELETE FROM receta_productos WHERE plato_id = %s", (producto_id,))
    if insumos:
        conn.execute(
            """INSERT INTO receta_insumos (producto_id, insumo_id, cantidad)
               SELECT %s, x.insumo_id, x.cantidad
                 FROM unnest(%s::uuid[], %s::numeric[]) AS x(insumo_id, cantidad)""",
            (producto_id, [r["insumo_id"] for r in insumos], [r["cantidad"] for r in insumos]),
        )
    if productos:
        conn.execute(
            """INSERT INTO receta_productos (plato_id, producto_id, cantidad)
               SELECT %s, x.producto_id, x.cantidad
                 FROM unnest(%s::uuid[], %s::numeric[]) AS x(producto_id, cantidad)""",
            (producto_id, [r["producto_id"] for r in productos], [r["cantidad"] for r in productos]),
        )


def _lineas_actuales(conn, tabla: str, columna_padre: str, columna_hijo: str, padre_id) -> dict:
    """{componente: cantidad} de una receta o combo. Nombres de tabla y
    columnas fijos de este módulo, nunca del cliente."""
    return {r[columna_hijo]: r["cantidad"] for r in conn.execute(
        f"SELECT {columna_hijo}, cantidad FROM {tabla} WHERE {columna_padre} = %s", (padre_id,))}


def crear_articulo(conn, actor: Usuario, datos: dict) -> dict:
    """datos: tipo, nombre, categoria_id, precio_venta, impuesto_id (opcional) y
    lo del subtipo: producto (codigo, precio_costo, stock_minimo, stock inicial,
    receta), combo (descripcion, productos, grupos), adicional (insumo_id, cantidad)."""
    tipo = datos["tipo"]
    _exigir_permiso_tipo(actor, tipo)
    impuesto_id = datos.get("impuesto_id") or _impuesto_por_defecto(conn, tipo, datos["categoria_id"])
    articulo_id = conn.execute(
        """INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (tipo, datos["nombre"], datos["categoria_id"], impuesto_id, datos["precio_venta"]),
    ).fetchone()["id"]

    if tipo == "producto":
        conn.execute(
            """INSERT INTO productos (articulo_id, codigo, precio_costo, stock, stock_minimo)
               VALUES (%s, %s, %s, %s, %s)""",
            (articulo_id, datos.get("codigo"), datos.get("precio_costo") or 0,
             datos.get("stock") or 0, datos.get("stock_minimo") or 0),
        )
        if datos.get("receta"):
            _guardar_receta(conn, articulo_id, datos["receta"])
    elif tipo == "combo":
        conn.execute("INSERT INTO combos (articulo_id, descripcion) VALUES (%s, %s)",
                     (articulo_id, datos.get("descripcion")))
        _guardar_productos_combo(conn, articulo_id, datos.get("productos") or [])
        if datos.get("grupos"):
            _guardar_grupos_combo(conn, articulo_id, datos["grupos"])
        _exigir_contenido_combo(conn, articulo_id)
    elif tipo == "adicional":
        if not datos.get("insumo_id") or not datos.get("cantidad"):
            raise ErrorNegocio("Un adicional necesita el insumo y la cantidad de la porción.")
        conn.execute("INSERT INTO adicionales (articulo_id, insumo_id, cantidad) VALUES (%s, %s, %s)",
                     (articulo_id, datos["insumo_id"], datos["cantidad"]))
    else:
        conn.execute("INSERT INTO servicios (articulo_id) VALUES (%s)", (articulo_id,))

    stock = f", stock inicial {datos['stock']}" if tipo == "producto" and datos.get("stock") else ""
    auditar(conn, actor.id, "inventario",
            f"Creó el {NOMBRE_TIPO[tipo]} {datos['nombre']} a ${datos['precio_venta']}{stock}", "articulos", articulo_id)
    return obtener_articulo(conn, articulo_id)


def editar_articulo(conn, actor: Usuario, articulo_id, cambios: dict) -> dict:
    """cambios: campos del artículo y de su subtipo (el tipo no cambia), y
    `productos` y `grupos` (combo) o `receta` (producto) para reemplazarlos."""
    # Primero el bloqueo, después la lectura: así el "antes" con el que se
    # compara y se audita no lo puede cambiar otra edición en paralelo.
    if conn.execute("SELECT 1 FROM articulos WHERE id = %s FOR UPDATE", (articulo_id,)).fetchone() is None:
        raise NoEncontrado("El artículo no existe.")
    antes = conn.execute("SELECT * FROM v_articulos WHERE id = %s", (articulo_id,)).fetchone()
    tipo = antes["tipo"]
    _exigir_permiso_tipo(actor, tipo)

    articulo = {k: v for k, v in cambios.items() if k in CAMPOS_ARTICULO and antes[k] != v}
    subtipo = {k: v for k, v in cambios.items() if k in CAMPOS_SUBTIPO[tipo]}
    if tipo == "adicional":
        subtipo = {k: v for k, v in subtipo.items() if antes[f"adicional_{k}"] != v}
    else:
        subtipo = {k: v for k, v in subtipo.items() if antes[k] != v}
    # Repetidos se rechazan siempre, cambie o no la receta.
    if cambios.get("receta"):
        _receta_sin_duplicados(cambios["receta"])
    if cambios.get("productos"):
        _sin_duplicados(cambios["productos"], "producto_id", "El combo")
    if cambios.get("grupos"):
        _validar_grupos(cambios["grupos"])
    # La pantalla manda la receta / los productos completos: solo cuentan si cambian.
    receta_nueva = (tipo == "producto" and "receta" in cambios
                    and _receta_actual(conn, articulo_id) != {_clave_receta(r): r["cantidad"] for r in cambios["receta"]})
    combo_nuevo = (tipo == "combo" and "productos" in cambios
                   and _lineas_actuales(conn, "combo_productos", "combo_id", "producto_id", articulo_id)
                   != {p["producto_id"]: p["cantidad"] for p in cambios["productos"]})
    grupos_nuevos = (tipo == "combo" and "grupos" in cambios
                     and _grupos_actuales(conn, articulo_id) != _grupos_pedidos(cambios["grupos"]))
    if "precio_costo" in subtipo and antes["tiene_receta"] and not (receta_nueva and not cambios["receta"]):
        raise ErrorNegocio("El costo de un plato con receta se calcula solo: edita la receta o quítala.")

    actualizar(conn, "articulos", articulo_id, articulo)
    if subtipo:
        actualizar(conn, TABLA_SUBTIPO[tipo], articulo_id, subtipo, pk="articulo_id")
    detalle = [f"{k}: {antes.get(k) if k in antes else antes.get('adicional_' + k)} → {v}"
               for k, v in {**articulo, **subtipo}.items()]
    if combo_nuevo:
        _guardar_productos_combo(conn, articulo_id, cambios["productos"])
        detalle.append("productos del combo")
    if grupos_nuevos:
        _guardar_grupos_combo(conn, articulo_id, cambios["grupos"])
        detalle.append("opciones para elegir" if cambios["grupos"] else "quitó las opciones para elegir")
    if combo_nuevo or grupos_nuevos:
        _exigir_contenido_combo(conn, articulo_id)
    if receta_nueva:
        _guardar_receta(conn, articulo_id, cambios["receta"])
        detalle.append("receta" if cambios["receta"] else "quitó la receta")
    if detalle:
        auditar(conn, actor.id, "inventario", f"Editó {antes['nombre']}: {'; '.join(detalle)}", "articulos", articulo_id)
    return obtener_articulo(conn, articulo_id)


def ajustar_stock(conn, actor: Usuario, producto_id, contado: Decimal, motivo: str) -> dict:
    """Fija el stock al conteo físico y deja el antes y el después en la auditoría."""
    fila = conn.execute(
        """SELECT p.stock, a.nombre FROM productos p JOIN articulos a ON a.id = p.articulo_id
            WHERE p.articulo_id = %s FOR UPDATE OF p""",
        (producto_id,),
    ).fetchone()
    if fila is None:
        raise NoEncontrado("El producto no existe.")
    conn.execute("UPDATE productos SET stock = %s WHERE articulo_id = %s", (contado, producto_id))
    auditar(conn, actor.id, "inventario",
            f"Ajustó el stock de {fila['nombre']}: {fila['stock']} → {contado} ({motivo})", "articulos", producto_id)
    return obtener_articulo(conn, producto_id)


# ── Insumos y preparaciones ─────────────────────────────────────────────────

def listar_insumos(conn, solo_activos: bool = False, texto: str | None = None) -> list[dict]:
    return conn.execute(
        """SELECT * FROM v_insumos
            WHERE (NOT %(solo_activos)s OR activo)
              AND (%(patron)s::text IS NULL OR """ + BUSCAR_NOMBRE + """)
            ORDER BY activo DESC, nombre""",
        {"solo_activos": solo_activos, "patron": literal_like(texto)},
    ).fetchall()


def crear_insumo(conn, actor: Usuario, nombre: str, unidad_medida_id, costo_unitario: Decimal,
                 stock: Decimal | None = None, stock_minimo: Decimal | None = None) -> dict:
    fila = conn.execute(
        """INSERT INTO insumos (nombre, unidad_medida_id, costo_unitario, stock, stock_minimo)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (nombre, unidad_medida_id, costo_unitario, stock or 0, stock_minimo or 0),
    ).fetchone()
    inicial = f", stock inicial {stock}" if stock else ""
    auditar(conn, actor.id, "inventario", f"Creó el insumo {nombre} a ${costo_unitario} por unidad{inicial}",
            "insumos", fila["id"])
    return conn.execute("SELECT * FROM v_insumos WHERE id = %s", (fila["id"],)).fetchone()


def editar_insumo(conn, actor: Usuario, insumo_id, cambios: dict) -> dict:
    """cambios: nombre, unidad_medida_id, costo_unitario, stock_minimo y/o
    activo. Cambiar el costo recalcula (en la base) el costo de los platos que
    lo usan. El stock no se edita aquí: se ajusta con ajustar_stock_insumo."""
    if conn.execute("SELECT 1 FROM insumos WHERE id = %s FOR UPDATE", (insumo_id,)).fetchone() is None:
        raise NoEncontrado("El insumo no existe.")
    antes = conn.execute("SELECT * FROM v_insumos WHERE id = %s", (insumo_id,)).fetchone()
    cambios = {k: v for k, v in cambios.items() if antes[k] != v}
    if "costo_unitario" in cambios and antes["es_preparacion"]:
        raise ErrorNegocio("El costo de una preparación se calcula con su receta y rendimiento.")
    actualizar(conn, "insumos", insumo_id, cambios)
    if cambios:
        detalle = "; ".join(f"{k}: {antes[k]} → {v}" for k, v in cambios.items())
        auditar(conn, actor.id, "inventario", f"Editó el insumo {antes['nombre']}: {detalle}", "insumos", insumo_id)
    return conn.execute("SELECT * FROM v_insumos WHERE id = %s", (insumo_id,)).fetchone()


def ajustar_stock_insumo(conn, actor: Usuario, insumo_id, contado: Decimal, motivo: str) -> dict:
    """Fija el stock del insumo al conteo físico; el antes y el después quedan en auditoría."""
    fila = conn.execute("SELECT nombre, stock FROM insumos WHERE id = %s FOR UPDATE", (insumo_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("El insumo no existe.")
    conn.execute("UPDATE insumos SET stock = %s WHERE id = %s", (contado, insumo_id))
    auditar(conn, actor.id, "inventario",
            f"Ajustó el stock de {fila['nombre']}: {fila['stock']} → {contado} ({motivo})", "insumos", insumo_id)
    return conn.execute("SELECT * FROM v_insumos WHERE id = %s", (insumo_id,)).fetchone()


def producir(conn, actor: Usuario, insumo_id, lotes: Decimal, notas: str | None = None) -> dict:
    """Produce lotes de una preparación: descuenta sus ingredientes (receta ×
    lotes) y suma lotes × rendimiento a su stock (lo hace la base). Un
    ingrediente puede quedar en negativo: la cocina produce y avisa."""
    prep = conn.execute(
        """SELECT i.nombre, i.activo, p.rendimiento, u.simbolo AS unidad
             FROM preparaciones p JOIN insumos i ON i.id = p.insumo_id
             JOIN unidades_medida u ON u.id = i.unidad_medida_id
            WHERE p.insumo_id = %s FOR UPDATE OF p""", (insumo_id,)).fetchone()
    if prep is None:
        raise NoEncontrado("La preparación no existe.")
    if not prep["activo"]:
        raise ErrorNegocio(f"{prep['nombre']} está inactiva.")
    cantidad = (lotes * prep["rendimiento"]).quantize(Decimal("0.001"))
    if cantidad <= 0:
        raise ErrorNegocio("Lo producido debe ser mayor que cero.")
    conn.execute(
        "INSERT INTO producciones (preparacion_id, lotes, cantidad, usuario_id, notas) VALUES (%s, %s, %s, %s, %s)",
        (insumo_id, lotes, cantidad, actor.id, notas),
    )
    auditar(conn, actor.id, "inventario",
            f"Produjo {lotes.normalize():f} lote(s) de {prep['nombre']}: {cantidad.normalize():f} {prep['unidad']}",
            "insumos", insumo_id)
    return listar_preparaciones(conn, insumo_id)[0]


def listar_producciones(conn, insumo_id) -> list[dict]:
    return conn.execute(
        """SELECT pr.id, pr.lotes, pr.cantidad, pr.creada_en, pr.notas, u.usuario
             FROM producciones pr JOIN usuarios u ON u.id = pr.usuario_id
            WHERE pr.preparacion_id = %s ORDER BY pr.creada_en DESC LIMIT 20""",
        (insumo_id,),
    ).fetchall()


def listar_preparaciones(conn, insumo_id=None) -> list[dict]:
    return conn.execute(
        """SELECT i.*,
                  COALESCE((SELECT json_agg(json_build_object(
                                'insumo_id', c.id, 'nombre', c.nombre, 'unidad', c.unidad,
                                'cantidad', r.cantidad, 'costo_unit', c.costo, 'stock', c.stock) ORDER BY c.nombre)
                              FROM receta_preparacion r JOIN v_insumos c ON c.id = r.insumo_id
                             WHERE r.preparacion_id = i.id), '[]') AS receta
             FROM v_insumos i
            WHERE i.es_preparacion AND (%s::uuid IS NULL OR i.id = %s)
            ORDER BY i.activo DESC, i.nombre""",
        (insumo_id, insumo_id),
    ).fetchall()


def guardar_preparacion(conn, actor: Usuario, insumo_id, rendimiento: Decimal, receta: list[dict]) -> dict:
    """Convierte el insumo en preparación (o la actualiza): rendimiento por
    lote y su receta. La base rechaza ciclos y recalcula los platos."""
    nombre = conn.execute("SELECT nombre FROM insumos WHERE id = %s FOR UPDATE", (insumo_id,)).fetchone()
    if nombre is None:
        raise NoEncontrado("El insumo no existe.")
    if not receta:
        raise ErrorNegocio("Una preparación necesita al menos un componente.")
    _sin_duplicados(receta, "insumo_id", "La receta")
    conn.execute(
        """INSERT INTO preparaciones (insumo_id, rendimiento) VALUES (%s, %s)
           ON CONFLICT (insumo_id) DO UPDATE SET rendimiento = EXCLUDED.rendimiento""",
        (insumo_id, rendimiento),
    )
    conn.execute("DELETE FROM receta_preparacion WHERE preparacion_id = %s", (insumo_id,))
    conn.execute(
        """INSERT INTO receta_preparacion (preparacion_id, insumo_id, cantidad)
           SELECT %s, x.insumo_id, x.cantidad
             FROM unnest(%s::uuid[], %s::numeric[]) AS x(insumo_id, cantidad)""",
        (insumo_id, [r["insumo_id"] for r in receta], [r["cantidad"] for r in receta]),
    )
    auditar(conn, actor.id, "inventario",
            f"Guardó la preparación {nombre['nombre']}: rinde {rendimiento}, {len(receta)} componentes",
            "insumos", insumo_id)
    return listar_preparaciones(conn, insumo_id)[0]


def crear_preparacion(conn, actor: Usuario, nombre: str, unidad_medida_id, rendimiento: Decimal,
                      receta: list[dict]) -> dict:
    insumo = crear_insumo(conn, actor, nombre, unidad_medida_id, Decimal(0))
    return guardar_preparacion(conn, actor, insumo["id"], rendimiento, receta)


def quitar_preparacion(conn, actor: Usuario, insumo_id) -> None:
    """La preparación vuelve a ser un insumo comprado (con su costo_unitario)."""
    fila = conn.execute(
        """SELECT i.nombre FROM preparaciones p JOIN insumos i ON i.id = p.insumo_id
            WHERE p.insumo_id = %s FOR UPDATE OF p""", (insumo_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("La preparación no existe.")
    # Se queda con el último costo calculado como costo a mano: si no, los
    # platos que la usan bajarían de costo sin que nadie lo note.
    costo = conn.execute(
        "UPDATE insumos SET costo_unitario = round(costo_insumo(id), 4) WHERE id = %s RETURNING costo_unitario",
        (insumo_id,)).fetchone()["costo_unitario"]
    conn.execute("DELETE FROM receta_preparacion WHERE preparacion_id = %s", (insumo_id,))
    conn.execute("DELETE FROM preparaciones WHERE insumo_id = %s", (insumo_id,))
    auditar(conn, actor.id, "inventario",
            f"Quitó la receta de la preparación {fila['nombre']}: queda con costo fijo ${costo} por unidad",
            "insumos", insumo_id)
