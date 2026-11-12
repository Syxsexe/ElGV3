"""
pos_api/servicios/cuentas.py — Cuentas abiertas por mesa o por nombre.

Una cuenta junta consumos que se cobran después. Cada ítem guarda el precio
del momento en que se agregó. Al cobrarla, sus ítems pasan a una venta (y la
cuenta queda apuntando a ella); al cancelarla, conserva lo que se canceló.
Cerrada (cobrada o cancelada) ya no cambia: lo hace cumplir la base.

Agregar consumos no se audita (es el día a día); quitarlos y cancelar una
cuenta con consumos sí, porque es plata que deja de cobrarse.
"""
from decimal import Decimal

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado
from pos_api.seguridad import Usuario
from pos_api.servicios import combos
from pos_api.servicios.comun import pesos
from pos_api.servicios.ventas import exigir_cliente, exigir_combos_vendibles, registrar_venta

# Va a cocina (comandas): ci = cuenta_items, a = su artículo, c = su categoría.
# Un combo va si lleva algún producto de cocina, fijo o elegido.
DE_COCINA = """(c.tipo = 'cocina' OR EXISTS (
    SELECT 1 FROM combo_productos cp JOIN articulos pa ON pa.id = cp.producto_id
      JOIN categorias pc ON pc.id = pa.categoria_id
     WHERE cp.combo_id = a.id AND pc.tipo = 'cocina') OR EXISTS (
    SELECT 1 FROM cuenta_item_elecciones e JOIN articulos pa ON pa.id = e.producto_id
      JOIN categorias pc ON pc.id = pa.categoria_id
     WHERE e.item_id = ci.id AND pc.tipo = 'cocina'))"""

# Nombre de un ítem con lo elegido: "Combo hamburguesa — Coca-Cola".
NOMBRE_ITEM = "a.nombre || COALESCE(' — ' || texto_elecciones(NULL, ci.id), '')"

_SELECT = """
    SELECT cu.id, cu.numero, cu.mesa_id, m.nombre AS mesa, cu.cliente_id, t.nombre AS cliente, cu.alias,
           COALESCE(t.nombre, cu.alias) AS nombre, cu.abierta_en, u.usuario AS abierta_por, cu.notas,
           cu.estado, cu.total_items AS total, cu.cancelada_en, cu.venta_id, v.numero AS venta_numero,
           (SELECT count(*) FROM cuenta_items ci WHERE ci.cuenta_id = cu.id) AS lineas
      FROM v_cuentas cu
      JOIN usuarios u ON u.id = cu.abierta_por
      LEFT JOIN mesas m ON m.id = cu.mesa_id
      LEFT JOIN terceros t ON t.id = cu.cliente_id
      LEFT JOIN ventas v ON v.id = cu.venta_id
"""


def _quien(cuenta: dict) -> str:
    """"mesa 3, Juan": la mesa y el nombre (una vez si el alias es la mesa)."""
    partes = [f"mesa {cuenta['mesa']}"] if cuenta.get("mesa") else []
    if cuenta.get("nombre") and cuenta["nombre"] != cuenta.get("mesa"):
        partes.append(cuenta["nombre"])
    return ", ".join(partes)


def _nombre(cuenta: dict) -> str:
    """"la cuenta #4 (mesa 3, Juan)" para mensajes y auditoría."""
    return f"la cuenta #{cuenta['numero']} ({_quien(cuenta)})"


def _cant(cantidad) -> str:
    return f"{Decimal(cantidad).normalize():f}"


def listar_abiertas(conn) -> list[dict]:
    return conn.execute(
        _SELECT + """
         WHERE cu.estado = 'abierta'
         ORDER BY m.nombre IS NULL, length(m.nombre), m.nombre, cu.numero"""
    ).fetchall()


def obtener_cuenta(conn, cuenta_id) -> dict:
    cuenta = conn.execute(_SELECT + " WHERE cu.id = %s", (cuenta_id,)).fetchone()
    if cuenta is None:
        raise NoEncontrado("La cuenta no existe.")
    cuenta["items"] = conn.execute(
        f"""SELECT ci.id, ci.articulo_id, {NOMBRE_ITEM} AS nombre, texto_elecciones(NULL, ci.id) AS elecciones,
                  ci.cantidad, ci.precio_unit,
                  round(ci.cantidad * ci.precio_unit, 2) AS subtotal, ci.agregado_en,
                  ci.enviado, {DE_COCINA} AS de_cocina
             FROM cuenta_items ci JOIN articulos a ON a.id = ci.articulo_id
             JOIN categorias c ON c.id = a.categoria_id
            WHERE ci.cuenta_id = %s ORDER BY ci.agregado_en, ci.id""",
        (cuenta_id,),
    ).fetchall()
    return cuenta


def _tomar_abierta(conn, cuenta_id) -> dict:
    """Bloquea la cuenta (dos pantallas no la cobran o cancelan a la vez) y
    exige que siga abierta."""
    fila = conn.execute("SELECT id FROM cuentas WHERE id = %s FOR UPDATE", (cuenta_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("La cuenta no existe.")
    cuenta = conn.execute(_SELECT + " WHERE cu.id = %s", (cuenta_id,)).fetchone()
    if cuenta["estado"] == "cobrada":
        raise ErrorNegocio(f"La cuenta #{cuenta['numero']} ya se cobró (venta #{cuenta['venta_numero']}).")
    if cuenta["estado"] == "cancelada":
        raise ErrorNegocio(f"La cuenta #{cuenta['numero']} ya se canceló.")
    return cuenta


def _exigir_mesa(conn, mesa_id) -> None:
    mesa = conn.execute("SELECT nombre, activa FROM mesas WHERE id = %s", (mesa_id,)).fetchone()
    if mesa is None:
        raise NoEncontrado("La mesa no existe.")
    if not mesa["activa"]:
        raise ErrorNegocio(f"La mesa {mesa['nombre']} está desactivada.")


# ── Abrir y editar ──────────────────────────────────────────────────────────

def abrir_cuenta(conn, actor: Usuario, mesa_id=None, cliente_id=None, alias: str | None = None,
                 notas: str | None = None) -> dict:
    """A nombre de un cliente registrado o de un alias (uno de los dos), con
    mesa opcional (una mesa tiene a lo sumo una cuenta abierta)."""
    if cliente_id is None and alias is None:
        raise ErrorNegocio("Escribe un nombre para la cuenta o elige un cliente.")
    if mesa_id is not None:
        _exigir_mesa(conn, mesa_id)
    if cliente_id is not None:
        exigir_cliente(conn, cliente_id)
        alias = None
    fila = conn.execute(
        """INSERT INTO cuentas (mesa_id, cliente_id, alias, abierta_por, notas)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (mesa_id, cliente_id, alias, actor.id, notas),
    ).fetchone()
    cuenta = obtener_cuenta(conn, fila["id"])
    auditar(conn, actor.id, "cuenta", f"Abrió {_nombre(cuenta)}", "cuentas", cuenta["id"])
    return cuenta


def editar_cuenta(conn, actor: Usuario, cuenta_id, cambios: dict) -> dict:
    """cambios: mesa_id (None = sin mesa), cliente_id o alias (poner uno quita
    el otro) y/o notas."""
    antes = _tomar_abierta(conn, cuenta_id)
    columnas = {}
    if "mesa_id" in cambios and cambios["mesa_id"] != antes["mesa_id"]:
        # Solo se valida una mesa nueva: la actual puede haberse desactivado
        # después de abrir la cuenta y eso no impide renombrarla.
        if cambios["mesa_id"] is not None:
            _exigir_mesa(conn, cambios["mesa_id"])
        columnas["mesa_id"] = cambios["mesa_id"]
    if cambios.get("cliente_id") is not None:
        exigir_cliente(conn, cambios["cliente_id"])
        columnas |= {"cliente_id": cambios["cliente_id"], "alias": None}
    elif cambios.get("alias") is not None:
        columnas |= {"cliente_id": None, "alias": cambios["alias"]}
    if "notas" in cambios:
        columnas["notas"] = cambios["notas"]
    if columnas:
        conn.execute(
            "UPDATE cuentas SET " + ", ".join(f"{c} = %({c})s" for c in columnas) + " WHERE id = %(id)s",
            columnas | {"id": cuenta_id},
        )
    cuenta = obtener_cuenta(conn, cuenta_id)
    if _quien(cuenta) != _quien(antes):
        auditar(conn, actor.id, "cuenta", f"Cambió {_nombre(antes)}: ahora {_quien(cuenta)}", "cuentas", cuenta_id)
    return cuenta


# ── Consumos ────────────────────────────────────────────────────────────────

def _exigir_stock(conn, cuenta_id, articulos: list) -> None:
    """Los productos de tienda que llevan los artículos indicados (ellos mismos,
    los fijos de su combo o lo elegido en él) deben alcanzar para todo lo que
    la cuenta tiene de ellos. Es un aviso temprano: al cobrar, la base vuelve a
    exigirlo con bloqueo."""
    falta = conn.execute(
        """WITH tocados AS (SELECT unnest(%(articulos)s::uuid[]) AS producto_id
                            UNION SELECT producto_id FROM combo_productos WHERE combo_id = ANY(%(articulos)s)),
                lleva AS (SELECT ci.articulo_id AS producto_id, ci.cantidad
                            FROM cuenta_items ci WHERE ci.cuenta_id = %(cuenta)s
                          UNION ALL
                          SELECT cp.producto_id, cp.cantidad * ci.cantidad
                            FROM cuenta_items ci JOIN combo_productos cp ON cp.combo_id = ci.articulo_id
                           WHERE ci.cuenta_id = %(cuenta)s
                          UNION ALL
                          SELECT e.producto_id, e.cantidad * ci.cantidad
                            FROM cuenta_items ci JOIN cuenta_item_elecciones e ON e.item_id = ci.id
                           WHERE ci.cuenta_id = %(cuenta)s)
           SELECT a.nombre, p.stock, sum(l.cantidad) AS cantidad
             FROM lleva l
             JOIN productos p ON p.articulo_id = l.producto_id
             JOIN articulos a ON a.id = l.producto_id
             JOIN categorias c ON c.id = a.categoria_id
            WHERE l.producto_id IN (SELECT producto_id FROM tocados) AND a.tipo = 'producto' AND c.tipo = 'tienda'
            GROUP BY a.nombre, p.stock
           HAVING sum(l.cantidad) > p.stock
            ORDER BY a.nombre""",
        {"cuenta": cuenta_id, "articulos": articulos},
    ).fetchall()
    if falta:
        raise ErrorNegocio("No hay stock suficiente de " + ", ".join(
            f"{f['nombre']} (hay {_cant(max(f['stock'], 0))}, la cuenta lleva {_cant(f['cantidad'])})" for f in falta))


def agregar_item(conn, actor: Usuario, cuenta_id, articulo_id, cantidad: Decimal,
                 elecciones: list[dict] | None = None) -> dict:
    """Agrega al precio actual (más los recargos de lo elegido, en un combo con
    grupos). Si ya hay una línea del mismo artículo, a ese mismo precio y con
    lo mismo elegido, le suma la cantidad en vez de repetirla."""
    _tomar_abierta(conn, cuenta_id)
    articulo = conn.execute(
        """SELECT id, tipo, nombre, activo, precio_venta, CASE WHEN tipo = 'combo' THEN combo_bloqueo(id) END AS bloqueo
             FROM articulos WHERE id = %s""",
        (articulo_id,)).fetchone()
    if articulo is None:
        raise NoEncontrado("El artículo no existe.")
    if not articulo["activo"]:
        raise ErrorNegocio(f"{articulo['nombre']} ya no se vende.")
    exigir_combos_vendibles([articulo])
    foto = combos.resolver(conn, articulo, elecciones)
    precio = articulo["precio_venta"] + combos.recargo(foto)

    iguales = [r["id"] for r in conn.execute(
        """SELECT id FROM cuenta_items WHERE cuenta_id = %s AND articulo_id = %s AND precio_unit = %s ORDER BY id""",
        (cuenta_id, articulo_id, precio))]
    fotos = combos.fotos_de_items(conn, "cuenta_item_elecciones", "item_id", iguales) if iguales else {}
    igual = next((i for i in iguales if combos.firma(fotos[i]) == combos.firma(foto)), None)
    if igual is not None:
        conn.execute("UPDATE cuenta_items SET cantidad = cantidad + %s WHERE id = %s", (cantidad, igual))
    else:
        item_id = conn.execute(
            "INSERT INTO cuenta_items (cuenta_id, articulo_id, cantidad, precio_unit) VALUES (%s, %s, %s, %s) RETURNING id",
            (cuenta_id, articulo_id, cantidad, precio),
        ).fetchone()["id"]
        combos.insertar_fotos(conn, "cuenta_item_elecciones", "item_id", {item_id: foto})
    _exigir_stock(conn, cuenta_id, [articulo_id] + [e["producto_id"] for e in foto])
    return obtener_cuenta(conn, cuenta_id)


def _item(conn, cuenta_id, item_id) -> dict:
    item = conn.execute(
        f"""SELECT ci.articulo_id, ci.cantidad, ci.precio_unit, {NOMBRE_ITEM} AS nombre,
                   ARRAY(SELECT e.producto_id FROM cuenta_item_elecciones e WHERE e.item_id = ci.id) AS elegidos
              FROM cuenta_items ci JOIN articulos a ON a.id = ci.articulo_id
             WHERE ci.id = %s AND ci.cuenta_id = %s""",
        (item_id, cuenta_id),
    ).fetchone()
    if item is None:
        raise NoEncontrado("Ese consumo ya no está en la cuenta.")
    return item


def cambiar_cantidad(conn, actor: Usuario, cuenta_id, item_id, cantidad: Decimal) -> dict:
    cuenta = _tomar_abierta(conn, cuenta_id)
    item = _item(conn, cuenta_id, item_id)
    # Si bajan por debajo de lo ya mandado a cocina, lo enviado baja con la
    # línea: lo que se agregue después vuelve a quedar pendiente.
    conn.execute("UPDATE cuenta_items SET cantidad = %s, enviado = LEAST(enviado, %s) WHERE id = %s",
                 (cantidad, cantidad, item_id))
    if cantidad > item["cantidad"]:
        _exigir_stock(conn, cuenta_id, [item["articulo_id"], *item["elegidos"]])
    if cantidad < item["cantidad"]:
        auditar(conn, actor.id, "cuenta",
                f"Bajó {item['nombre']} de {_cant(item['cantidad'])} a {_cant(cantidad)} en {_nombre(cuenta)}",
                "cuentas", cuenta_id)
    return obtener_cuenta(conn, cuenta_id)


def quitar_item(conn, actor: Usuario, cuenta_id, item_id) -> dict:
    cuenta = _tomar_abierta(conn, cuenta_id)
    item = _item(conn, cuenta_id, item_id)
    conn.execute("DELETE FROM cuenta_items WHERE id = %s", (item_id,))
    auditar(conn, actor.id, "cuenta",
            f"Quitó {_cant(item['cantidad'])} × {item['nombre']} ({pesos(item['cantidad'] * item['precio_unit'])}) "
            f"de {_nombre(cuenta)}", "cuentas", cuenta_id)
    return obtener_cuenta(conn, cuenta_id)


# ── Cerrar ──────────────────────────────────────────────────────────────────

def cobrar_cuenta(conn, actor: Usuario, cuenta_id, sesion_id, *, descuento: Decimal, pagos: list[dict],
                  fiado: Decimal, cliente_id=None, notas: str | None = None) -> dict:
    """Pasa los ítems a una venta en el turno indicado y cierra la cuenta. El
    cliente de la venta es el indicado o, si no, el de la cuenta. Los pagos
    deben cubrir el total actual: si alguien agregó un consumo mientras se
    cobraba, falla con el total nuevo en vez de cobrar de menos."""
    cuenta = _tomar_abierta(conn, cuenta_id)
    items = conn.execute(
        "SELECT id, articulo_id, cantidad, precio_unit FROM cuenta_items WHERE cuenta_id = %s ORDER BY agregado_en, id",
        (cuenta_id,),
    ).fetchall()
    if not items:
        raise ErrorNegocio(f"La cuenta #{cuenta['numero']} no tiene consumos: cancélala si ya no se usa.")
    # Lo elegido en cada combo pasa a la venta tal como se pidió (con su recargo).
    fotos = combos.fotos_de_items(conn, "cuenta_item_elecciones", "item_id", [i["id"] for i in items])
    items = [{"articulo_id": i["articulo_id"], "cantidad": i["cantidad"], "precio_unit": i["precio_unit"],
              "foto_elecciones": fotos[i["id"]]} for i in items]
    venta = registrar_venta(conn, actor, sesion_id, items, descuento=descuento, pagos=pagos, fiado=fiado,
                            cliente_id=cliente_id or cuenta["cliente_id"], notas=notas, origen=_nombre(cuenta),
                            exigir_activos=False)
    # Los ítems se mueven: la cuenta cobrada no conserva líneas (0006).
    conn.execute("DELETE FROM cuenta_items WHERE cuenta_id = %s", (cuenta_id,))
    conn.execute("UPDATE cuentas SET venta_id = %s WHERE id = %s", (venta["id"], cuenta_id))
    venta["cuenta_id"], venta["cuenta_numero"], venta["mesa"] = cuenta["id"], cuenta["numero"], cuenta["mesa"]
    return venta


def cancelar_cuenta(conn, actor: Usuario, cuenta_id, motivo: str | None) -> dict:
    """Cierra la cuenta sin cobrar. Con consumos exige el motivo (queda en las
    notas y en la auditoría); vacía (abierta por error) no."""
    cuenta = _tomar_abierta(conn, cuenta_id)
    if cuenta["lineas"] and not motivo:
        raise ErrorNegocio(f"La cuenta tiene consumos por {pesos(cuenta['total'])}: escribe por qué se cancela.")
    conn.execute(
        """UPDATE cuentas SET cancelada_en = now(),
                  notas = CASE WHEN %(motivo)s::text IS NULL THEN notas
                               ELSE concat_ws(E'\\n', notas, 'Cancelada: ' || %(motivo)s) END
            WHERE id = %(id)s""",
        {"motivo": motivo, "id": cuenta_id},
    )
    detalle = f"Canceló {_nombre(cuenta)}"
    if cuenta["lineas"]:
        detalle += f" con consumos por {pesos(cuenta['total'])}"
    if motivo:
        detalle += f": {motivo}"
    auditar(conn, actor.id, "cuenta", detalle, "cuentas", cuenta_id)
    return obtener_cuenta(conn, cuenta_id)
