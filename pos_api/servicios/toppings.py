"""
pos_api/servicios/toppings.py — Toppings de los platos.

Un plato de cocina acepta toppings: adicionales (insumo + porción + precio)
que se agregan o no al pedirlo, una vez cada uno. Lo agregado viaja con la
línea como una foto (adicional y precio cobrado) que no cambia aunque después
se edite el plato o el adicional. El precio de la línea es el del plato más
el de sus toppings; el stock de sus insumos lo mueve la base (0025).
"""
from decimal import Decimal

from pos_api.errores import ErrorNegocio


def del_plato(conn, plato_id, solo_activos: bool = False) -> list[dict]:
    """Los toppings que acepta el plato, con lo que hace falta para venderlos
    (precio, activo) y para el editor (insumo, porción, costo)."""
    return conn.execute(
        """SELECT pt.adicional_id, a.nombre, a.precio_venta AS precio, a.activo,
                  i.nombre AS insumo, ad.cantidad AS porcion, u.simbolo AS unidad,
                  round(ad.cantidad * costo_insumo(ad.insumo_id), 2) AS costo
             FROM plato_toppings pt
             JOIN articulos a ON a.id = pt.adicional_id
             JOIN adicionales ad ON ad.articulo_id = pt.adicional_id
             JOIN insumos i ON i.id = ad.insumo_id
             JOIN unidades_medida u ON u.id = i.unidad_medida_id
            WHERE pt.plato_id = %s AND (NOT %s OR a.activo)
            ORDER BY pt.orden, a.nombre""",
        (plato_id, solo_activos),
    ).fetchall()


def guardar_del_plato(conn, plato_id, adicionales: list) -> None:
    """Reemplaza los toppings que acepta el plato (en el orden recibido). El
    topping se cobra dentro de la línea del plato, con el impuesto del plato:
    por eso debe tener el mismo impuesto."""
    if len(set(adicionales)) != len(adicionales):
        raise ErrorNegocio("Un topping está repetido en el plato.")
    if adicionales:
        validos = conn.execute(
            """SELECT ad.articulo_id, a.nombre, i.codigo AS impuesto, i.id AS impuesto_id
                 FROM adicionales ad JOIN articulos a ON a.id = ad.articulo_id JOIN impuestos i ON i.id = a.impuesto_id
                WHERE ad.articulo_id = ANY(%s)""", (adicionales,)).fetchall()
        if len(validos) != len(adicionales):
            raise ErrorNegocio("Un topping no es un adicional (crea primero el adicional en Inventario).")
        plato = conn.execute(
            "SELECT a.impuesto_id, i.codigo FROM articulos a JOIN impuestos i ON i.id = a.impuesto_id WHERE a.id = %s",
            (plato_id,)).fetchone()
        otro = next((t for t in validos if t["impuesto_id"] != plato["impuesto_id"]), None)
        if otro:
            raise ErrorNegocio(f"{otro['nombre']} tiene otro impuesto ({otro['impuesto']}) que el plato ({plato['codigo']}): "
                               "un topping se cobra con el impuesto del plato.")
    conn.execute("DELETE FROM plato_toppings WHERE plato_id = %s", (plato_id,))
    if adicionales:
        conn.execute(
            """INSERT INTO plato_toppings (plato_id, adicional_id, orden)
               SELECT %s, x.id, x.n FROM unnest(%s::uuid[]) WITH ORDINALITY AS x(id, n)""",
            (plato_id, adicionales),
        )


def actuales(conn, plato_id) -> list:
    """Los adicionales que acepta el plato, en orden (para saber si cambiaron)."""
    return [r["adicional_id"] for r in conn.execute(
        "SELECT adicional_id FROM plato_toppings WHERE plato_id = %s ORDER BY orden, adicional_id", (plato_id,))]


def resolver(conn, articulo: dict, pedidos: list | None) -> list[dict]:
    """Valida los toppings pedidos para `articulo` ({id, nombre}) y retorna la
    foto [{adicional_id, nombre, precio}] en el orden del plato."""
    pedidos = list(pedidos or [])
    if not pedidos:
        return []
    if len(set(pedidos)) != len(pedidos):
        raise ErrorNegocio(f"En {articulo['nombre']} un topping se pidió dos veces.")
    aceptados = {t["adicional_id"]: t for t in conn.execute(
        """SELECT pt.adicional_id, a.nombre, a.precio_venta AS precio, a.activo, p.toppings_incluidos
             FROM plato_toppings pt JOIN articulos a ON a.id = pt.adicional_id
             JOIN productos p ON p.articulo_id = pt.plato_id
            WHERE pt.plato_id = %s ORDER BY pt.orden, a.nombre""", (articulo["id"],))}
    if not aceptados:
        raise ErrorNegocio(f"{articulo['nombre']} no lleva toppings.")
    foto = []
    for t in aceptados.values():
        if t["adicional_id"] not in pedidos:
            continue
        if not t["activo"]:
            raise ErrorNegocio(f"{t['nombre']} ya no se vende: quítalo de {articulo['nombre']}.")
        foto.append({"adicional_id": t["adicional_id"], "nombre": t["nombre"], "precio": t["precio"]})
    if len(foto) != len(pedidos):
        raise ErrorNegocio(f"Uno de los toppings ya no está en {articulo['nombre']}: vuelve a elegirlos.")
    return aplicar_incluidos(foto, next(iter(aceptados.values()))["toppings_incluidos"])


def exigir_incluidos(conn, plato_id) -> None:
    """Los toppings incluidos no pueden ser más que los que acepta el plato
    (un producto sin toppings queda con 0)."""
    fila = conn.execute(
        """SELECT p.toppings_incluidos AS incluidos, (SELECT count(*) FROM plato_toppings WHERE plato_id = p.articulo_id) AS n
             FROM productos p WHERE p.articulo_id = %s""", (plato_id,)).fetchone()
    if fila and fila["incluidos"] > fila["n"]:
        raise ErrorNegocio(f"Van {fila['incluidos']} toppings incluidos y el plato solo acepta {fila['n']}: "
                           "baja los incluidos o agrega toppings.")


def aplicar_incluidos(foto: list[dict], incluidos: int) -> list[dict]:
    """Los `incluidos` toppings más baratos van sin costo (precio 0 en la foto);
    los demás se cobran. A igual precio, gana el orden del plato."""
    gratis = sorted(range(len(foto)), key=lambda i: (Decimal(foto[i]["precio"]), i))[:incluidos]
    return [{**t, "precio": Decimal(0)} if i in gratis else t for i, t in enumerate(foto)]


def total(foto: list[dict]) -> Decimal:
    return sum((Decimal(t["precio"]) for t in foto), Decimal(0))


def firma(foto: list[dict]) -> frozenset:
    """Lo que hace iguales dos líneas del mismo plato (para sumarlas): los
    mismos toppings al mismo precio."""
    return frozenset((t["adicional_id"], Decimal(t["precio"])) for t in foto)


def es_topping_suelto(conn, articulo_ids: list) -> str | None:
    """El nombre del primer adicional de la lista que es topping de algún plato
    activo (no se vende suelto), o None."""
    fila = conn.execute(
        """SELECT a.nombre FROM articulos a
            WHERE a.id = ANY(%s) AND a.tipo = 'adicional'
              AND EXISTS (SELECT 1 FROM plato_toppings pt JOIN articulos pa ON pa.id = pt.plato_id
                           WHERE pt.adicional_id = a.id AND pa.activo)
            ORDER BY a.nombre LIMIT 1""", (articulo_ids,)).fetchone()
    return fila["nombre"] if fila else None


def fotos_de_items(conn, tabla: str, columna: str, ids: list) -> dict:
    """{línea: foto} de los toppings de varias líneas. tabla y columna son
    fijas de este módulo (cuenta_item_toppings/item_id), nunca del cliente."""
    resultado = {i: [] for i in ids}
    for t in conn.execute(
        f"""SELECT t.{columna} AS linea, t.adicional_id, a.nombre, t.precio
              FROM {tabla} t JOIN articulos a ON a.id = t.adicional_id
             WHERE t.{columna} = ANY(%s) ORDER BY a.nombre""",
        (ids,),
    ):
        resultado[t.pop("linea")].append(t)
    return resultado


def insertar_fotos(conn, tabla: str, columna: str, por_linea: dict) -> None:
    """Guarda los toppings de varias líneas en una sola sentencia."""
    filas = [(linea, t["adicional_id"], Decimal(t["precio"])) for linea, foto in por_linea.items() for t in foto]
    if not filas:
        return
    conn.execute(
        f"""INSERT INTO {tabla} ({columna}, adicional_id, precio)
            SELECT * FROM unnest(%s::uuid[], %s::uuid[], %s::numeric[])""",
        tuple(list(col) for col in zip(*filas)),
    )
