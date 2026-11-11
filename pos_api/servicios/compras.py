"""
pos_api/servicios/compras.py — Compras a proveedores.

Una compra trae líneas de productos o insumos con lo pagado por unidad
(impuestos incluidos). Al registrarla el stock de tienda sube por trigger y
se actualiza el último costo: el de cada insumo (lo que recalcula los platos)
y el de cada producto. Los platos con receta y las preparaciones no se compran:
su costo lo calcula la base. Lo pagado sale de los egresos que la pagan
(servicios/egresos.py) y lo pendiente es la cuenta por pagar (v_compras).

Corregir una compra = borrarla (si no tiene pagos) y registrarla de nuevo:
borrarla devuelve el stock, pero no los costos anteriores.

Todo exige compras.registrar.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado
from pos_api.seguridad import Usuario
from pos_api.servicios.comun import condicion_busqueda, literal_like, pesos

SOPORTES = {"factura_electronica": "factura electrónica", "factura": "factura", "pos": "tiquete POS", "otro": "otro"}

_COMPRA = """
    SELECT vc.id, vc.numero, vc.proveedor_id, t.nombre AS proveedor, vc.registrada_en, vc.tipo_soporte,
           vc.numero_soporte, vc.cufe, vc.fecha_soporte, vc.notas, vc.total, vc.base, vc.impuestos, vc.pagado,
           vc.pendiente, u.usuario,
           (SELECT count(*) FROM compra_lineas cl WHERE cl.compra_id = vc.id) AS lineas,
           EXISTS (SELECT 1 FROM clientes cl WHERE cl.tercero_id = vc.proveedor_id) AS proveedor_es_cliente
      FROM v_compras vc
      JOIN terceros t ON t.id = vc.proveedor_id
      JOIN usuarios u ON u.id = vc.usuario_id
"""


# ── Consultas ───────────────────────────────────────────────────────────────

def items_compra(conn, texto: str | None = None, limite: int = 40) -> list[dict]:
    """Lo que se compra: productos (sin receta: el costo de un plato con receta
    lo calcula la base) e insumos, activos, con su último costo."""
    return conn.execute(
        f"""SELECT * FROM (
                SELECT 'producto' AS tipo, a.id, a.nombre, p.precio_costo AS costo, a.impuesto_id,
                       'und' AS unidad, c.tipo AS categoria_tipo, p.codigo
                  FROM articulos a
                  JOIN productos p ON p.articulo_id = a.id
                  JOIN categorias c ON c.id = a.categoria_id
                 WHERE a.activo AND NOT EXISTS (SELECT 1 FROM receta_insumos r WHERE r.producto_id = a.id)
                UNION ALL
                SELECT 'insumo', i.id, i.nombre, i.costo_unitario, NULL, u.simbolo, NULL, NULL
                  FROM insumos i JOIN unidades_medida u ON u.id = i.unidad_medida_id
                 WHERE i.activo AND NOT EXISTS (SELECT 1 FROM preparaciones pr WHERE pr.insumo_id = i.id)
            ) x
            WHERE %(patron)s::text IS NULL OR {condicion_busqueda("x.nombre")} OR x.codigo = %(texto)s
            ORDER BY x.nombre
            LIMIT %(limite)s""",
        {"patron": literal_like(texto), "texto": (texto or "").strip(), "limite": limite},
    ).fetchall()


def listar_compras(conn, *, proveedor_id=None, solo_pendientes: bool = False, desde: date | None = None,
                   hasta: date | None = None, limite: int = 200) -> list[dict]:
    return conn.execute(
        _COMPRA + """
         WHERE (%(prov)s::uuid IS NULL OR vc.proveedor_id = %(prov)s)
           AND (NOT %(pend)s OR vc.pendiente > 0)
           AND (%(desde)s::date IS NULL OR vc.registrada_en >= %(desde)s::date)
           AND (%(hasta)s::date IS NULL OR vc.registrada_en < %(hasta)s::date + 1)
         ORDER BY vc.registrada_en DESC, vc.numero DESC
         LIMIT %(limite)s""",
        {"prov": proveedor_id, "pend": solo_pendientes, "desde": desde, "hasta": hasta, "limite": limite},
    ).fetchall()


def por_pagar(conn) -> dict:
    """Cuentas por pagar agrupadas por proveedor, la más vieja primero."""
    proveedores = conn.execute(
        """SELECT vc.proveedor_id, t.nombre AS proveedor, sum(vc.pendiente) AS pendiente, count(*) AS compras,
                  min(vc.registrada_en) AS desde
             FROM v_compras vc JOIN terceros t ON t.id = vc.proveedor_id
            WHERE vc.pendiente > 0
            GROUP BY vc.proveedor_id, t.nombre
            ORDER BY min(vc.registrada_en)"""
    ).fetchall()
    return {"total": sum((p["pendiente"] for p in proveedores), Decimal(0)), "proveedores": proveedores}


def detalle_compra(conn, compra_id) -> dict:
    compra = conn.execute(_COMPRA + " WHERE vc.id = %s", (compra_id,)).fetchone()
    if compra is None:
        raise NoEncontrado("La compra no existe.")
    compra["items"] = conn.execute(
        """SELECT cl.id, CASE WHEN cl.producto_id IS NOT NULL THEN 'producto' ELSE 'insumo' END AS tipo,
                  COALESCE(cl.producto_id, cl.insumo_id) AS item_id, COALESCE(a.nombre, i.nombre) AS nombre,
                  COALESCE(u.simbolo, 'und') AS unidad, cl.cantidad, cl.costo_unit, im.codigo AS impuesto,
                  round(cl.cantidad * cl.costo_unit, 2) AS subtotal
             FROM compra_lineas cl
             LEFT JOIN articulos a ON a.id = cl.producto_id
             LEFT JOIN insumos i ON i.id = cl.insumo_id
             LEFT JOIN unidades_medida u ON u.id = i.unidad_medida_id
             LEFT JOIN impuestos im ON im.id = cl.impuesto_id
            WHERE cl.compra_id = %s ORDER BY cl.id""",
        (compra_id,),
    ).fetchall()
    compra["pagos"] = conn.execute(
        """SELECT ve.id, ve.creado_en, ve.concepto, ve.monto, ve.pagado, ve.cruzado, ve.anulado, u.usuario,
                  s.numero AS turno
             FROM v_egresos ve
             JOIN usuarios u ON u.id = ve.usuario_id
             JOIN sesiones_caja s ON s.id = ve.sesion_id
            WHERE ve.compra_id = %s ORDER BY ve.creado_en, ve.id""",
        (compra_id,),
    ).fetchall()
    return compra


# ── Escritura ───────────────────────────────────────────────────────────────

def _exigir_proveedor(conn, proveedor_id) -> str:
    fila = conn.execute(
        """SELECT t.nombre, pr.activo FROM proveedores pr JOIN terceros t ON t.id = pr.tercero_id
            WHERE pr.tercero_id = %s""", (proveedor_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("El proveedor no existe.")
    if not fila["activo"]:
        raise ErrorNegocio(f"{fila['nombre']} está desactivado como proveedor.")
    return fila["nombre"]


def registrar_compra(conn, actor: Usuario, proveedor_id, lineas: list[dict], *, tipo_soporte: str = "otro",
                     numero_soporte: str | None = None, cufe: str | None = None,
                     fecha_soporte: date | None = None, notas: str | None = None) -> dict:
    """lineas = [{producto_id | insumo_id, cantidad, costo_unit, impuesto_id?}].
    Retorna el detalle con `costos_actualizados` (qué último costo cambió)."""
    proveedor = _exigir_proveedor(conn, proveedor_id)
    if not lineas:
        raise ErrorNegocio("La compra no tiene líneas.")
    if tipo_soporte == "factura_electronica" and not cufe:
        raise ErrorNegocio("Una factura electrónica lleva su CUFE.")
    claves = [("producto", l["producto_id"]) if l.get("producto_id") else ("insumo", l["insumo_id"]) for l in lineas]
    if len(claves) != len(set(claves)):
        raise ErrorNegocio("Un producto o insumo aparece dos veces: junta las cantidades en una sola línea.")

    productos = {c for t, c in claves if t == "producto"}
    insumos = {c for t, c in claves if t == "insumo"}
    # Lo que se compra es lo mismo que ofrece items_compra: activo, productos
    # sin receta e insumos que no son preparaciones (de esos el costo y el
    # stock los calcula la base). Trae el costo de antes para decir qué cambió.
    antes = {f["id"]: f for f in conn.execute(
        """SELECT a.id, a.nombre, p.precio_costo AS costo, a.activo,
                  EXISTS (SELECT 1 FROM receta_insumos r WHERE r.producto_id = a.id) AS calculado
             FROM articulos a JOIN productos p ON p.articulo_id = a.id
            WHERE a.id = ANY(%s)
           UNION ALL
           SELECT i.id, i.nombre, i.costo_unitario, i.activo,
                  EXISTS (SELECT 1 FROM preparaciones pr WHERE pr.insumo_id = i.id)
             FROM insumos i WHERE i.id = ANY(%s)""",
        (list(productos), list(insumos)))}
    if len(antes) != len(claves):
        raise NoEncontrado("Uno de los productos o insumos no existe.")
    inactivos = sorted(f["nombre"] for f in antes.values() if not f["activo"])
    if inactivos:
        raise ErrorNegocio(f"Están desactivados: {', '.join(inactivos)}.")
    calculados = sorted(f["nombre"] for f in antes.values() if f["calculado"])
    if calculados:
        raise ErrorNegocio(f"No se compran (tienen receta: se preparan aquí): {', '.join(calculados)}.")

    compra = conn.execute(
        """INSERT INTO compras (proveedor_id, usuario_id, tipo_soporte, numero_soporte, cufe, fecha_soporte, notas)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, numero""",
        (proveedor_id, actor.id, tipo_soporte, numero_soporte, cufe, fecha_soporte, notas),
    ).fetchone()
    # Todas las líneas en UN solo INSERT: el trigger de stock es por sentencia.
    conn.execute(
        """INSERT INTO compra_lineas (compra_id, producto_id, insumo_id, cantidad, costo_unit, impuesto_id)
           SELECT %s, x.producto, x.insumo, x.cantidad, x.costo, x.impuesto
             FROM unnest(%s::uuid[], %s::uuid[], %s::numeric[], %s::numeric[], %s::uuid[])
                  WITH ORDINALITY AS x(producto, insumo, cantidad, costo, impuesto, n)
            ORDER BY x.n""",
        (compra["id"], [l.get("producto_id") for l in lineas], [l.get("insumo_id") for l in lineas],
         [l["cantidad"] for l in lineas], [l["costo_unit"] for l in lineas], [l.get("impuesto_id") for l in lineas]),
    )

    # Último costo, redondeado como lo guarda la columna (2 decimales en
    # productos, 4 en insumos; la mitad se aleja del cero, como en Postgres).
    nuevos = {}
    for (_, c), l in zip(claves, lineas):
        nuevos[c] = Decimal(l["costo_unit"]).quantize(Decimal("0.01") if c in productos else Decimal("0.0001"),
                                                     rounding=ROUND_HALF_UP)
    cambios = [c for c in nuevos if nuevos[c] != antes[c]["costo"]]
    for tabla, columna, clave, ids in (("insumos", "costo_unitario", "id", [c for c in cambios if c in insumos]),
                                       ("productos", "precio_costo", "articulo_id", [c for c in cambios if c in productos])):
        if ids:
            conn.execute(
                f"""UPDATE {tabla} t SET {columna} = x.costo
                      FROM unnest(%s::uuid[], %s::numeric[]) AS x(id, costo) WHERE t.{clave} = x.id""",
                (ids, [nuevos[c] for c in ids]),
            )

    detalle = detalle_compra(conn, compra["id"])
    detalle["costos_actualizados"] = [
        {"nombre": antes[c]["nombre"], "antes": antes[c]["costo"], "ahora": nuevos[c]} for c in cambios]
    soporte = SOPORTES[tipo_soporte] + (f" {numero_soporte}" if numero_soporte else "")
    texto = f"Registró la compra #{compra['numero']} a {proveedor} por {pesos(detalle['total'])} ({soporte})"
    if cambios:
        texto += f"; actualizó el costo de {len(cambios)} producto(s) o insumo(s)"
    auditar(conn, actor.id, "compra", texto, "compras", compra["id"])
    return detalle


def borrar_compra(conn, actor: Usuario, compra_id) -> None:
    """Para corregir una compra mal registrada. Con pagos (aunque estén
    anulados) no se borra: quedan referenciados en la caja."""
    compra = conn.execute(
        """SELECT co.numero, t.nombre FROM compras co JOIN terceros t ON t.id = co.proveedor_id
            WHERE co.id = %s FOR UPDATE OF co""", (compra_id,)).fetchone()
    if compra is None:
        raise NoEncontrado("La compra no existe.")
    if conn.execute("SELECT 1 FROM egresos WHERE compra_id = %s LIMIT 1", (compra_id,)).fetchone():
        raise ErrorNegocio(f"La compra #{compra['numero']} tiene pagos registrados: no se puede borrar.")
    total = conn.execute("SELECT total FROM v_compras WHERE id = %s", (compra_id,)).fetchone()["total"]
    # Las líneas en una sola sentencia: el trigger de stock lo devuelve todo junto.
    conn.execute("DELETE FROM compra_lineas WHERE compra_id = %s", (compra_id,))
    conn.execute("DELETE FROM compras WHERE id = %s", (compra_id,))
    auditar(conn, actor.id, "compra",
            f"Borró la compra #{compra['numero']} a {compra['nombre']} por {pesos(total)} (el stock se devolvió)",
            "compras", compra_id)
