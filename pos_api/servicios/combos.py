"""
pos_api/servicios/combos.py — Lo que se elige al pedir un combo con grupos.

Un combo puede tener grupos ("Bebida") de los que se elige una opción al
venderlo. Lo elegido viaja con la línea como una foto (grupo, producto,
unidades por combo y recargo) que no cambia aunque después se edite el combo.
La venta directa y las cuentas mandan lo que tocó el cajero (grupo_id y
producto_id); aquí se valida contra el combo actual y se arma la foto.
"""
from decimal import Decimal

from pos_api.errores import ErrorNegocio


def grupos(conn, combo_id, solo_activas: bool = False) -> list[dict]:
    """Grupos del combo con sus opciones. Cada opción trae lo que hace falta
    para mostrarla al vender (activo, unidades disponibles) y para el editor
    (costo, stock, tipo de categoría)."""
    filas = conn.execute(
        """SELECT g.id, g.nombre, g.cantidad, g.orden
             FROM combo_grupos g WHERE g.combo_id = %s ORDER BY g.orden, g.nombre""",
        (combo_id,),
    ).fetchall()
    opciones = conn.execute(
        """SELECT o.grupo_id, o.producto_id, a.nombre, o.recargo, a.activo, p.precio_costo AS costo_unit,
                  p.stock, c.tipo AS categoria_tipo, unidades_disponibles(o.producto_id) AS disponibles
             FROM combo_opciones o
             JOIN combo_grupos g ON g.id = o.grupo_id
             JOIN articulos a ON a.id = o.producto_id
             JOIN productos p ON p.articulo_id = o.producto_id
             JOIN categorias c ON c.id = a.categoria_id
            WHERE g.combo_id = %s AND (NOT %s OR a.activo)
            ORDER BY o.recargo, a.nombre""",
        (combo_id, solo_activas),
    ).fetchall()
    for g in filas:
        g["opciones"] = [{k: v for k, v in o.items() if k != "grupo_id"} for o in opciones if o["grupo_id"] == g["id"]]
    return filas


def resolver(conn, combo: dict, pedidas: list[dict] | None, *, desde_cuenta: bool = False) -> list[dict]:
    """Valida lo elegido para `combo` ({id, nombre, tipo}) y retorna la foto:
    [{grupo, producto_id, nombre, cantidad, recargo}] en el orden de los grupos.
    pedidas = [{grupo_id, producto_id}]: una opción activa por grupo.
    desde_cuenta: la línea viene de una cuenta o un documento armados antes de
    que el combo tuviera grupos (el mensaje dice cómo arreglarlo)."""
    pedidas = pedidas or []
    if combo["tipo"] != "combo":
        if pedidas:
            raise ErrorNegocio(f"{combo['nombre']} no es un combo: no lleva opciones para elegir.")
        return []
    lista = grupos(conn, combo["id"])
    if not lista:
        if pedidas:
            raise ErrorNegocio(f"{combo['nombre']} ya no tiene opciones para elegir: vuelve a agregarlo.")
        return []

    elegido = {}
    for p in pedidas:
        if p["grupo_id"] in elegido:
            raise ErrorNegocio(f"En {combo['nombre']} se eligió dos veces en el mismo grupo.")
        elegido[p["grupo_id"]] = p["producto_id"]
    if set(elegido) - {g["id"] for g in lista}:
        raise ErrorNegocio(f"Las opciones de {combo['nombre']} cambiaron: vuelve a elegir.")
    faltan = [g["nombre"] for g in lista if g["id"] not in elegido]
    if faltan:
        if desde_cuenta:
            raise ErrorNegocio(f"{combo['nombre']} ahora pide elegir {', '.join(faltan)}: "
                               "quítalo y vuelve a agregarlo.")
        raise ErrorNegocio(f"Elige {', '.join(faltan)} para {combo['nombre']}.")

    foto = []
    for g in lista:
        opcion = next((o for o in g["opciones"] if o["producto_id"] == elegido[g["id"]]), None)
        if opcion is None:
            raise ErrorNegocio(f"Esa opción ya no está en {g['nombre']} de {combo['nombre']}: vuelve a elegir.")
        if not opcion["activo"]:
            raise ErrorNegocio(f"{opcion['nombre']} ya no se vende: elige otra opción de {g['nombre']}.")
        foto.append({"grupo": g["nombre"], "producto_id": opcion["producto_id"], "nombre": opcion["nombre"],
                     "cantidad": g["cantidad"], "recargo": opcion["recargo"]})
    return foto


def recargo(foto: list[dict]) -> Decimal:
    return sum((Decimal(e["recargo"]) for e in foto), Decimal(0))


def firma(foto: list[dict]) -> frozenset:
    """Lo que hace iguales dos líneas del mismo combo (para sumarlas)."""
    return frozenset((e["grupo"], e["producto_id"], Decimal(e["cantidad"])) for e in foto)


def fotos_de_items(conn, tabla: str, columna: str, ids: list) -> dict:
    """{línea: foto} de lo elegido en varias líneas. tabla y columna son fijas
    de este módulo (cuenta_item_elecciones/item_id), nunca del cliente."""
    resultado = {i: [] for i in ids}
    for e in conn.execute(
        f"""SELECT e.{columna} AS linea, e.grupo, e.producto_id, a.nombre, e.cantidad, e.recargo
              FROM {tabla} e JOIN articulos a ON a.id = e.producto_id
             WHERE e.{columna} = ANY(%s) ORDER BY e.grupo""",
        (ids,),
    ):
        resultado[e.pop("linea")].append(e)
    return resultado


def insertar_fotos(conn, tabla: str, columna: str, por_linea: dict) -> None:
    """Guarda lo elegido de varias líneas en una sola sentencia."""
    filas = [(linea, e["grupo"], e["producto_id"], Decimal(e["cantidad"]), Decimal(e["recargo"]))
             for linea, foto in por_linea.items() for e in foto]
    if not filas:
        return
    conn.execute(
        f"""INSERT INTO {tabla} ({columna}, grupo, producto_id, cantidad, recargo)
            SELECT * FROM unnest(%s::uuid[], %s::text[], %s::uuid[], %s::numeric[], %s::numeric[])""",
        tuple(list(col) for col in zip(*filas)),
    )
