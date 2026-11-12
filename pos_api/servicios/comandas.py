"""
pos_api/servicios/comandas.py — Comandas: lo que se manda a cocina desde una cuenta.

Van a cocina los artículos de categoría cocina y los combos que llevan algo
de cocina. Cada ítem de la cuenta recuerda cuánto ya se envió (enviado): la
comanda nueva trae solo lo pendiente. Si bajan la cantidad por debajo de lo
enviado, lo enviado baja con ella (cuentas.cambiar_cantidad): lo que se agregue
después vuelve a quedar pendiente.

La comanda guarda su copia (artículo, lo elegido en el combo, cantidad,
comentario) para reimprimirla aunque la cuenta ya se haya cobrado.
"""
from decimal import Decimal

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado
from pos_api.seguridad import Usuario
from pos_api.servicios.cuentas import DE_COCINA, NOMBRE_ITEM, _cant, _nombre, _tomar_abierta

# Lo que lleva de cocina un combo, para que en la comanda se vea qué preparar.
COMPONENTES = """(SELECT string_agg(trim_scale(cp.cantidad) || ' × ' || pa.nombre, ', ' ORDER BY pa.nombre)
    FROM combo_productos cp JOIN articulos pa ON pa.id = cp.producto_id
    JOIN categorias pc ON pc.id = pa.categoria_id
   WHERE cp.combo_id = a.id AND pc.tipo = 'cocina')"""


def pendientes(conn, cuenta_id) -> list[dict]:
    return conn.execute(
        f"""SELECT ci.id, ci.articulo_id, {NOMBRE_ITEM} AS nombre, texto_elecciones(NULL, ci.id) AS elecciones,
                   ci.cantidad, ci.enviado,
                   ci.cantidad - ci.enviado AS pendiente, {COMPONENTES} AS componentes
              FROM cuenta_items ci
              JOIN articulos a ON a.id = ci.articulo_id
              JOIN categorias c ON c.id = a.categoria_id
             WHERE ci.cuenta_id = %s AND ci.cantidad > ci.enviado AND {DE_COCINA}
             ORDER BY ci.agregado_en, ci.id""",
        (cuenta_id,),
    ).fetchall()


_COMANDAS = """
    SELECT co.id, co.numero, co.creada_en, co.notas, u.usuario,
           cu.id AS cuenta_id, cu.numero AS cuenta_numero, m.nombre AS mesa,
           COALESCE(t.nombre, cu.alias) AS nombre
      FROM comandas co
      JOIN usuarios u ON u.id = co.usuario_id
      JOIN cuentas cu ON cu.id = co.cuenta_id
      LEFT JOIN mesas m ON m.id = cu.mesa_id
      LEFT JOIN terceros t ON t.id = cu.cliente_id
"""


def _con_items(conn, comandas: list[dict]) -> list[dict]:
    """Les pone sus ítems a varias comandas con una sola consulta."""
    items = conn.execute(
        f"""SELECT ci.comanda_id, ci.id, a.nombre || COALESCE(' — ' || ci.elecciones, '') AS nombre,
                   ci.elecciones, ci.cantidad, ci.comentario, {COMPONENTES} AS componentes
              FROM comanda_items ci JOIN articulos a ON a.id = ci.articulo_id
             WHERE ci.comanda_id = ANY(%s) ORDER BY ci.id""",
        ([c["id"] for c in comandas],),
    ).fetchall()
    for c in comandas:
        c["items"] = [{k: v for k, v in i.items() if k != "comanda_id"} for i in items if i["comanda_id"] == c["id"]]
    return comandas


def detalle_comanda(conn, comanda_id) -> dict:
    comanda = conn.execute(_COMANDAS + " WHERE co.id = %s", (comanda_id,)).fetchone()
    if comanda is None:
        raise NoEncontrado("La comanda no existe.")
    return _con_items(conn, [comanda])[0]


def listar_comandas(conn, cuenta_id) -> list[dict]:
    if conn.execute("SELECT 1 FROM cuentas WHERE id = %s", (cuenta_id,)).fetchone() is None:
        raise NoEncontrado("La cuenta no existe.")
    comandas = conn.execute(
        _COMANDAS + " WHERE co.cuenta_id = %s ORDER BY co.numero DESC LIMIT 50", (cuenta_id,)
    ).fetchall()
    return _con_items(conn, comandas)


def crear_comanda(conn, actor: Usuario, cuenta_id, items: list[dict], notas: str | None = None) -> dict:
    """items = [{cuenta_item_id, cantidad, comentario}]: cada uno de cocina y
    sin pasar de lo pendiente."""
    cuenta = _tomar_abierta(conn, cuenta_id)
    if not items:
        raise ErrorNegocio("Elige qué mandar a cocina.")
    ids = [i["cuenta_item_id"] for i in items]
    if len(ids) != len(set(ids)):
        raise ErrorNegocio("Un consumo aparece dos veces en la comanda.")
    por_id = {p["id"]: p for p in pendientes(conn, cuenta_id)}
    for i in items:
        p = por_id.get(i["cuenta_item_id"])
        if p is None:
            raise ErrorNegocio("Uno de los consumos ya no está pendiente para cocina: vuelve a abrir la comanda.")
        if i["cantidad"] > p["pendiente"]:
            raise ErrorNegocio(f"De {p['nombre']} solo quedan {_cant(p['pendiente'])} por mandar a cocina.")

    comanda = conn.execute(
        "INSERT INTO comandas (cuenta_id, usuario_id, notas) VALUES (%s, %s, %s) RETURNING id, numero",
        (cuenta_id, actor.id, notas),
    ).fetchone()
    conn.cursor().executemany(
        "INSERT INTO comanda_items (comanda_id, articulo_id, elecciones, cantidad, comentario) VALUES (%s, %s, %s, %s, %s)",
        [(comanda["id"], por_id[i["cuenta_item_id"]]["articulo_id"], por_id[i["cuenta_item_id"]]["elecciones"],
          i["cantidad"], i.get("comentario")) for i in items],
    )
    conn.cursor().executemany(
        "UPDATE cuenta_items SET enviado = enviado + %s WHERE id = %s",
        [(i["cantidad"], i["cuenta_item_id"]) for i in items],
    )
    unidades = sum((Decimal(i["cantidad"]) for i in items), Decimal(0))
    auditar(conn, actor.id, "cuenta",
            f"Mandó a cocina la comanda #{comanda['numero']} ({_cant(unidades)} unidad(es)) de {_nombre(cuenta)}",
            "cuentas", cuenta_id)
    return detalle_comanda(conn, comanda["id"])
