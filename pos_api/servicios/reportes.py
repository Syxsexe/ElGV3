"""
pos_api/servicios/reportes.py — Tablero de Inicio y reportes del negocio.

Todo se calcula de las vistas y tablas de movimientos (nada guarda totales).
Los montos van con impuestos incluidos, como se cobran. Las fechas son días
completos en la hora del negocio (las conexiones usan ELG_ZONA_HORARIA).

- Ventas por categoría y productos van antes de descuentos (el descuento es
  de la venta, no de la línea); el resumen muestra los descuentos aparte.
- Resultado = ventas − costo de lo vendido − gastos − premios de torneos −
  fiado condonado (una venta fiada cuenta como ingreso; si la deuda se
  perdona, esa plata no llega). Los pagos de compras no son gasto: lo
  comprado entra al costo cuando se vende. Los egresos anulados no cuentan.
"""
from datetime import date
from decimal import Decimal

from pos_api.errores import ErrorNegocio
from pos_api.seguridad import Usuario
from pos_api.servicios.caja import id_turno_abierto

MAX_DIAS = 400


# ── Inicio ──────────────────────────────────────────────────────────────────

def inicio(conn, actor: Usuario) -> dict:
    turno = None
    sesion = id_turno_abierto(conn)
    if sesion:
        turno = conn.execute(
            """SELECT s.id, s.numero, s.abierta_en, u.usuario AS abierta_por,
                      (SELECT count(*) FROM ventas v WHERE v.sesion_id = s.id) AS ventas,
                      (SELECT COALESCE(sum(total), 0) FROM v_ventas v WHERE v.sesion_id = s.id) AS total
                 FROM sesiones_caja s JOIN usuarios u ON u.id = s.abierta_por WHERE s.id = %s""",
            (sesion,),
        ).fetchone()
        turno["cajas"] = conn.execute(
            """SELECT vs.caja, vs.esperado FROM v_sesion_cajas vs JOIN cajas c ON c.id = vs.caja_id
                WHERE vs.sesion_id = %s ORDER BY c.usa_denominaciones DESC, c.nombre""",
            (sesion,),
        ).fetchall()

    hoy = conn.execute(
        """SELECT count(*) AS ventas, COALESCE(sum(total), 0) AS total, COALESCE(sum(fiado), 0) AS fiado,
                  COALESCE(sum(total) FILTER (WHERE tipo = 'tienda'), 0) AS tienda,
                  COALESCE(sum(total) FILTER (WHERE tipo = 'cocina'), 0) AS cocina,
                  COALESCE(sum(total) FILTER (WHERE tipo = 'mixta'), 0) AS mixta
             FROM v_ventas WHERE creada_en >= current_date AND creada_en < current_date + 1"""
    ).fetchone()

    cuentas = conn.execute(
        """SELECT count(*) AS abiertas, COALESCE(sum(total_items), 0) AS total
             FROM v_cuentas WHERE estado = 'abierta'"""
    ).fetchone()

    bajo_minimo = conn.execute(
        """SELECT a.id, a.nombre, p.stock, p.stock_minimo, count(*) OVER () AS total
             FROM productos p JOIN articulos a ON a.id = p.articulo_id JOIN categorias c ON c.id = a.categoria_id
            WHERE a.activo AND c.tipo = 'tienda' AND p.stock_minimo > 0 AND p.stock <= p.stock_minimo
            ORDER BY p.stock - p.stock_minimo, a.nombre
            LIMIT 20"""
    ).fetchall()
    total_bajo = bajo_minimo[0]["total"] if bajo_minimo else 0

    # Fiado vencido: el total y los cinco clientes que más deben, sin traerlos a todos.
    vencidos = conn.execute(
        """WITH v AS (SELECT cliente_id, sum(pendiente) AS vencido, min(vence_en) AS desde
                        FROM v_cargos_credito WHERE vencido GROUP BY cliente_id)
           SELECT v.cliente_id, t.nombre, v.vencido, v.desde,
                  sum(v.vencido) OVER () AS total, count(*) OVER () AS clientes
             FROM v JOIN terceros t ON t.id = v.cliente_id
            ORDER BY v.vencido DESC
            LIMIT 5"""
    ).fetchall()

    datos = {
        "turno": turno,
        "hoy": hoy,
        "cuentas": cuentas,
        "bajo_minimo": {"total": total_bajo,
                        "productos": [{k: v for k, v in p.items() if k != "total"} for p in bajo_minimo]},
        "cartera_vencida": {"total": vencidos[0]["total"] if vencidos else Decimal(0),
                            "clientes": vencidos[0]["clientes"] if vencidos else 0,
                            "top": [{k: x for k, x in v.items() if k not in ("total", "clientes")} for v in vencidos]},
        "por_pagar": None,
    }
    if actor.puede("compras.registrar"):
        datos["por_pagar"] = conn.execute(
            "SELECT COALESCE(sum(pendiente), 0) AS total, count(*) FILTER (WHERE pendiente > 0) AS compras FROM v_compras"
        ).fetchone()
    return datos


# ── Reportes por rango ──────────────────────────────────────────────────────

def reporte(conn, desde: date, hasta: date) -> dict:
    if hasta < desde:
        raise ErrorNegocio("La fecha final es anterior a la inicial.")
    if (hasta - desde).days >= MAX_DIAS:
        raise ErrorNegocio(f"El rango máximo es de {MAX_DIAS} días.")
    r = {"desde": desde, "hasta": hasta}
    rango = {"desde": desde, "hasta": hasta}

    def en_rango(columna: str) -> str:
        return f"{columna} >= %(desde)s::date AND {columna} < %(hasta)s::date + 1"

    ventas = conn.execute(
        f"""SELECT count(*) AS cantidad, COALESCE(sum(subtotal), 0) AS subtotal,
                   COALESCE(sum(descuento), 0) AS descuentos, COALESCE(sum(total), 0) AS total,
                   COALESCE(sum(fiado), 0) AS fiado
              FROM v_ventas WHERE {en_rango('creada_en')}""", rango).fetchone()
    costo = conn.execute(
        f"""SELECT COALESCE(round(sum(d.cantidad * d.costo_unit), 2), 0) AS costo
              FROM detalle_venta d JOIN ventas v ON v.id = d.venta_id WHERE {en_rango('v.creada_en')}""", rango).fetchone()["costo"]
    gastos = conn.execute(
        f"""SELECT COALESCE(sum(monto), 0) AS total FROM v_egresos
             WHERE compra_id IS NULL AND NOT anulado AND {en_rango('creado_en')}""", rango).fetchone()["total"]
    condonado = conn.execute(
        f"SELECT COALESCE(sum(monto), 0) AS total FROM condonaciones_credito WHERE {en_rango('creado_en')}",
        rango).fetchone()["total"]
    torneos = conn.execute(
        """SELECT count(*) AS cantidad, COALESCE(sum(jugadores), 0) AS jugadores,
                  COALESCE(sum(recaudado), 0) AS recaudado, COALESCE(sum(costo_premios), 0) AS premios,
                  COALESCE(sum(ganancia), 0) AS ganancia
             FROM v_torneos WHERE realizado_en >= %(desde)s::date AND realizado_en < %(hasta)s::date + 1""",
        rango).fetchone()
    utilidad = ventas["total"] - costo
    r["resumen"] = {
        **ventas, "costo": costo, "utilidad_bruta": utilidad,
        "margen": round(utilidad / ventas["total"] * 100, 1) if ventas["total"] else None,
        "gastos": gastos, "premios": torneos["premios"], "condonado": condonado,
        "resultado": utilidad - gastos - torneos["premios"] - condonado,
    }
    r["torneos"] = torneos

    # Un renglón por día del rango, aunque no haya movimientos.
    r["por_dia"] = conn.execute(
        f"""WITH dias AS (SELECT d::date AS dia FROM generate_series(%(desde)s::date, %(hasta)s::date, interval '1 day') d),
                 v AS (SELECT creada_en::date AS dia, sum(total) AS ventas, count(*) AS cantidad
                         FROM v_ventas WHERE {en_rango('creada_en')} GROUP BY 1),
                 g AS (SELECT creado_en::date AS dia, sum(monto) AS gastos
                         FROM v_egresos WHERE compra_id IS NULL AND NOT anulado AND {en_rango('creado_en')} GROUP BY 1)
           SELECT dias.dia, COALESCE(v.ventas, 0) AS ventas, COALESCE(v.cantidad, 0) AS cantidad,
                  COALESCE(g.gastos, 0) AS gastos
             FROM dias LEFT JOIN v USING (dia) LEFT JOIN g USING (dia)
            ORDER BY dias.dia""", rango).fetchall()

    r["por_categoria"] = conn.execute(
        f"""SELECT c.nombre AS categoria, c.tipo, round(sum(d.cantidad), 3) AS unidades,
                   round(sum(d.cantidad * d.precio_unit), 2) AS ventas, round(sum(d.cantidad * d.costo_unit), 2) AS costo
              FROM detalle_venta d JOIN ventas v ON v.id = d.venta_id
              JOIN articulos a ON a.id = d.articulo_id JOIN categorias c ON c.id = a.categoria_id
             WHERE {en_rango('v.creada_en')}
             GROUP BY c.id, c.nombre, c.tipo
             ORDER BY sum(d.cantidad * d.precio_unit) DESC""", rango).fetchall()

    r["productos"] = conn.execute(
        f"""SELECT a.id, a.nombre, round(sum(d.cantidad), 3) AS unidades, round(sum(d.cantidad * d.precio_unit), 2) AS ventas,
                   round(sum(d.cantidad * d.costo_unit), 2) AS costo
              FROM detalle_venta d JOIN ventas v ON v.id = d.venta_id JOIN articulos a ON a.id = d.articulo_id
             WHERE {en_rango('v.creada_en')}
             GROUP BY a.id, a.nombre
             ORDER BY sum(d.cantidad * d.precio_unit) DESC
             LIMIT 10""", rango).fetchall()

    metodos = conn.execute(
        f"""SELECT mp.nombre AS metodo, sum(pv.monto) AS monto
              FROM pagos_venta pv JOIN ventas v ON v.id = pv.venta_id JOIN metodos_pago mp ON mp.id = pv.metodo_pago_id
             WHERE {en_rango('v.creada_en')}
             GROUP BY mp.nombre ORDER BY sum(pv.monto) DESC""", rango).fetchall()
    if ventas["fiado"]:
        metodos.append({"metodo": "Fiado", "monto": ventas["fiado"]})
    r["por_metodo"] = metodos

    r["gastos_por_categoria"] = conn.execute(
        f"""SELECT cg.nombre AS categoria, sum(ve.monto) AS monto
             FROM v_egresos ve JOIN categorias_gasto cg ON cg.id = ve.categoria_gasto_id
            WHERE NOT ve.anulado AND {en_rango('ve.creado_en')}
            GROUP BY cg.nombre ORDER BY sum(ve.monto) DESC""", rango).fetchall()
    return r
