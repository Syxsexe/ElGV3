"""
pos_api/servicios/conteo.py — Conteo físico de inventario desde la pantalla.

Quien cuenta ve el stock del sistema, escribe lo que contó y, si quiere, el
stock mínimo. Todo el conteo se guarda en una sola transacción, con las
mismas funciones de Inventario (cada ajuste y cada mínimo queda auditado).

Si el stock de una fila cambió mientras se contaba (una venta, una compra),
lo contado ya no corresponde a ese número: esa fila no se ajusta y vuelve en
`cambiaron` para recontarla. El mínimo sí se guarda, porque no depende del
stock.
"""
from decimal import Decimal

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado
from pos_api.seguridad import Usuario
from pos_api.servicios import catalogo

MOTIVO = "conteo físico"


def _actuales(conn, tipo: str, ids: list) -> dict:
    if tipo == "productos":
        filas = conn.execute(
            """SELECT a.id, a.nombre, c.tipo AS categoria_tipo, p.stock, p.stock_minimo
                 FROM articulos a
                 JOIN categorias c ON c.id = a.categoria_id
                 JOIN productos p ON p.articulo_id = a.id
                WHERE a.id = ANY(%s) ORDER BY a.id FOR UPDATE OF p""",
            (ids,),
        ).fetchall()
    else:
        filas = conn.execute(
            "SELECT id, nombre, stock, stock_minimo FROM insumos WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
            (ids,),
        ).fetchall()
    return {f["id"]: f for f in filas}


def registrar_conteo(conn, actor: Usuario, tipo: str, filas: list[dict]) -> dict:
    """filas: [{id, stock_visto, contado?, stock_minimo?}]. Devuelve lo
    ajustado, los mínimos cambiados y las filas que cambiaron mientras se
    contaba (sin ajustar)."""
    ids = [f["id"] for f in filas]
    if len(set(ids)) != len(ids):
        raise ErrorNegocio("El conteo trae el mismo artículo dos veces.")
    actuales = _actuales(conn, tipo, ids)
    if len(actuales) != len(ids):
        faltan = len(ids) - len(actuales)
        raise NoEncontrado(f"{faltan} {'artículo del conteo ya no existe' if faltan == 1 else 'artículos del conteo ya no existen'}: "
                           "se recargó la lista, revisa y vuelve a guardar.")
    if tipo == "productos":
        platos = [a["nombre"] for a in actuales.values() if a["categoria_tipo"] != "tienda"]
        if platos:
            raise ErrorNegocio(f"{platos[0]} es un plato de cocina: no lleva stock propio.")

    ajustar = catalogo.ajustar_stock if tipo == "productos" else catalogo.ajustar_stock_insumo
    resultado = {"ajustados": [], "minimos": [], "cambiaron": []}
    for f in filas:
        actual = actuales[f["id"]]
        contado = f.get("contado")
        if contado is not None:
            if Decimal(actual["stock"]) != Decimal(f["stock_visto"]):
                resultado["cambiaron"].append({"id": f["id"], "nombre": actual["nombre"],
                                               "visto": f["stock_visto"], "actual": actual["stock"]})
            elif Decimal(actual["stock"]) != Decimal(contado):
                ajustar(conn, actor, f["id"], contado, MOTIVO)
                resultado["ajustados"].append({"id": f["id"], "nombre": actual["nombre"],
                                               "antes": actual["stock"], "despues": contado})
        minimo = f.get("stock_minimo")
        if minimo is not None and Decimal(actual["stock_minimo"]) != Decimal(minimo):
            _fijar_minimo(conn, actor, tipo, actual, minimo)
            resultado["minimos"].append({"id": f["id"], "nombre": actual["nombre"],
                                         "antes": actual["stock_minimo"], "despues": minimo})
    return resultado


def _fijar_minimo(conn, actor: Usuario, tipo: str, actual: dict, minimo) -> None:
    """Directo sobre la fila ya bloqueada (productos o insumos), sin pasar por
    editar_articulo: ese bloquea primero `articulos` y, con una edición en
    paralelo, el orden distinto de los bloqueos podría trabar las dos."""
    tabla, clave, entidad = (("productos", "articulo_id", "articulos") if tipo == "productos"
                             else ("insumos", "id", "insumos"))
    conn.execute(f"UPDATE {tabla} SET stock_minimo = %s WHERE {clave} = %s", (minimo, actual["id"]))
    auditar(conn, actor.id, "inventario",
            f"Cambió el stock mínimo de {actual['nombre']}: {actual['stock_minimo']} → {minimo} ({MOTIVO})",
            entidad, actual["id"])
