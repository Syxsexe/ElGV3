"""
modules/reportes.py — El G POS
KPIs, reportes de ventas, inventario y caja. Solo accesible para admin.
"""

from database import get_connection
from auth import requiere_admin


# ════════════════════════════════════════════════════════════
# VENTAS
# ════════════════════════════════════════════════════════════

@requiere_admin
def reporte_ventas_por_periodo(
    fecha_inicio: str,
    fecha_fin: str,
    tipo: str = None
) -> dict:
    """
    Resumen de ventas entre dos fechas.
    Incluye totales, desglose por tipo, método de pago y vendedor.
    Fechas en formato 'YYYY-MM-DD'.
    """
    conn   = get_connection()
    params = [fecha_inicio, fecha_fin]

    filtro_tipo = ""
    if tipo:
        filtro_tipo = " AND v.tipo = ?"
        params.append(tipo)

    # Totales generales
    general = conn.execute(f"""
        SELECT
            COUNT(*)        AS num_ventas,
            SUM(total)      AS ingresos,
            SUM(descuento)  AS descuentos,
            AVG(total)      AS ticket_promedio
        FROM ventas v
        WHERE date(v.fecha) BETWEEN ? AND ?
        {filtro_tipo}
    """, params).fetchone()

    # Por tipo de negocio
    por_tipo = conn.execute(f"""
        SELECT tipo, COUNT(*) AS num, SUM(total) AS total
        FROM ventas v
        WHERE date(v.fecha) BETWEEN ? AND ?
        {filtro_tipo}
        GROUP BY tipo
    """, params).fetchall()

    # Por método de pago
    por_metodo = conn.execute(f"""
        SELECT metodo_pago, COUNT(*) AS num, SUM(total) AS total
        FROM ventas v
        WHERE date(v.fecha) BETWEEN ? AND ?
        {filtro_tipo}
        GROUP BY metodo_pago
        ORDER BY total DESC
    """, params).fetchall()

    # Por vendedor
    por_vendedor = conn.execute(f"""
        SELECT u.usuario, COUNT(*) AS num_ventas, SUM(v.total) AS total
        FROM ventas v
        JOIN usuarios u ON v.usuario_id = u.id
        WHERE date(v.fecha) BETWEEN ? AND ?
        {filtro_tipo}
        GROUP BY v.usuario_id
        ORDER BY total DESC
    """, params).fetchall()

    # Por día (para gráfica de tendencia)
    por_dia = conn.execute(f"""
        SELECT date(v.fecha) AS dia, COUNT(*) AS num, SUM(v.total) AS total
        FROM ventas v
        WHERE date(v.fecha) BETWEEN ? AND ?
        {filtro_tipo}
        GROUP BY dia
        ORDER BY dia
    """, params).fetchall()

    conn.close()
    return {
        "periodo":       {"inicio": fecha_inicio, "fin": fecha_fin},
        "general":       dict(general),
        "por_tipo":      [dict(r) for r in por_tipo],
        "por_metodo":    [dict(r) for r in por_metodo],
        "por_vendedor":  [dict(r) for r in por_vendedor],
        "por_dia":       [dict(r) for r in por_dia],
    }


@requiere_admin
def productos_mas_vendidos(
    fecha_inicio: str = None,
    fecha_fin: str    = None,
    tipo: str         = None,
    limite: int       = 10
) -> list:
    """
    Top productos más vendidos por cantidad y por ingresos.
    tipo: 'tienda' | 'cocina' | None (todos)
    """
    conn   = get_connection()
    params = []
    where  = ["dv.producto_id IS NOT NULL"]

    if fecha_inicio:
        where.append("date(v.fecha) >= ?")
        params.append(fecha_inicio)
    if fecha_fin:
        where.append("date(v.fecha) <= ?")
        params.append(fecha_fin)
    if tipo:
        where.append("c.tipo = ?")
        params.append(tipo)

    where_clause = " AND ".join(where)
    params.append(limite)

    filas = conn.execute(f"""
        SELECT
            p.nombre,
            c.nombre        AS categoria,
            c.tipo          AS tipo_negocio,
            SUM(dv.cantidad)  AS unidades_vendidas,
            SUM(dv.subtotal)  AS ingresos_totales,
            AVG(dv.precio_unit) AS precio_promedio
        FROM detalle_venta dv
        JOIN ventas    v ON dv.venta_id    = v.id
        JOIN productos p ON dv.producto_id = p.id
        JOIN categorias c ON p.categoria_id = c.id
        WHERE {where_clause}
        GROUP BY dv.producto_id
        ORDER BY unidades_vendidas DESC
        LIMIT ?
    """, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


@requiere_admin
def combos_mas_vendidos(
    fecha_inicio: str = None,
    fecha_fin: str    = None,
    limite: int       = 10
) -> list:
    """Top combos más vendidos."""
    conn   = get_connection()
    params = []
    where  = ["dv.combo_id IS NOT NULL"]

    if fecha_inicio:
        where.append("date(v.fecha) >= ?")
        params.append(fecha_inicio)
    if fecha_fin:
        where.append("date(v.fecha) <= ?")
        params.append(fecha_fin)

    where_clause = " AND ".join(where)
    params.append(limite)

    filas = conn.execute(f"""
        SELECT
            c.nombre,
            SUM(dv.cantidad)  AS veces_vendido,
            SUM(dv.subtotal)  AS ingresos_totales
        FROM detalle_venta dv
        JOIN ventas  v ON dv.venta_id = v.id
        JOIN combos  c ON dv.combo_id = c.id
        WHERE {where_clause}
        GROUP BY dv.combo_id
        ORDER BY veces_vendido DESC
        LIMIT ?
    """, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


@requiere_admin
def ventas_por_hora(fecha: str = None) -> list:
    """
    Distribución de ventas por hora del día.
    Útil para identificar horas pico.
    fecha: 'YYYY-MM-DD' | None (hoy)
    """
    from datetime import date
    if not fecha:
        fecha = date.today().isoformat()

    conn  = get_connection()
    filas = conn.execute("""
        SELECT
            strftime('%H', fecha) AS hora,
            COUNT(*)              AS num_ventas,
            SUM(total)            AS total
        FROM ventas
        WHERE date(fecha) = ?
        GROUP BY hora
        ORDER BY hora
    """, (fecha,)).fetchall()
    conn.close()
    return [dict(f) for f in filas]


# ════════════════════════════════════════════════════════════
# INVENTARIO
# ════════════════════════════════════════════════════════════

@requiere_admin
def reporte_inventario(tipo: str = None) -> dict:
    """
    Estado actual del inventario.
    Retorna valor total en stock, productos bajo mínimo y listado completo.
    tipo: 'tienda' | 'cocina' | None (todos)
    """
    conn   = get_connection()
    params = []
    where  = ["p.activo = 1"]
    if tipo:
        where.append("c.tipo = ?")
        params.append(tipo)
    where_clause = " AND ".join(where)

    # Valor total en inventario
    totales = conn.execute(f"""
        SELECT
            COUNT(*)                          AS total_productos,
            SUM(p.stock)                      AS unidades_totales,
            SUM(p.stock * p.precio_costo)     AS valor_costo,
            SUM(p.stock * p.precio_venta)     AS valor_venta
        FROM productos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE {where_clause}
    """, params).fetchone()

    # Productos bajo mínimo
    bajo_minimo = conn.execute(f"""
        SELECT p.nombre, c.nombre AS categoria, p.stock, p.stock_minimo,
               (p.stock_minimo - p.stock) AS faltante
        FROM productos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE {where_clause}
          AND p.stock_minimo > 0
          AND p.stock <= p.stock_minimo
        ORDER BY faltante DESC
    """, params).fetchall()

    # Listado completo con margen
    listado = conn.execute(f"""
        SELECT
            p.nombre, p.codigo, c.nombre AS categoria, c.tipo,
            p.stock, p.stock_minimo, p.precio_costo, p.precio_venta,
            CASE WHEN p.precio_costo > 0
                 THEN ROUND(((p.precio_venta - p.precio_costo) / p.precio_costo) * 100, 1)
                 ELSE 0 END AS margen_pct
        FROM productos p
        JOIN categorias c ON p.categoria_id = c.id
        WHERE {where_clause}
        ORDER BY c.tipo, c.nombre, p.nombre
    """, params).fetchall()

    conn.close()
    return {
        "totales":     dict(totales),
        "bajo_minimo": [dict(r) for r in bajo_minimo],
        "listado":     [dict(r) for r in listado],
    }


@requiere_admin
def reporte_insumos() -> dict:
    """Estado actual de insumos de cocina con alertas de stock bajo."""
    conn = get_connection()

    totales = conn.execute("""
        SELECT COUNT(*) AS total, SUM(stock) AS stock_total
        FROM insumos WHERE activo = 1
    """).fetchone()

    bajo_minimo = conn.execute("""
        SELECT nombre, stock, stock_minimo, unidad,
               (stock_minimo - stock) AS faltante
        FROM insumos
        WHERE activo = 1 AND stock_minimo > 0 AND stock <= stock_minimo
        ORDER BY faltante DESC
    """).fetchall()

    listado = conn.execute("""
        SELECT nombre, stock, stock_minimo, unidad
        FROM insumos WHERE activo = 1
        ORDER BY nombre
    """).fetchall()

    conn.close()
    return {
        "totales":     dict(totales),
        "bajo_minimo": [dict(r) for r in bajo_minimo],
        "listado":     [dict(r) for r in listado],
    }


# ════════════════════════════════════════════════════════════
# CAJA
# ════════════════════════════════════════════════════════════

@requiere_admin
def reporte_caja_por_periodo(
    fecha_inicio: str,
    fecha_fin: str
) -> dict:
    """
    Resumen de sesiones de caja en un rango de fechas.
    Incluye totales, diferencias y detalle por sesión.
    """
    conn   = get_connection()
    params = [fecha_inicio, fecha_fin]

    totales = conn.execute("""
        SELECT
            COUNT(*)            AS num_sesiones,
            SUM(monto_base)     AS suma_bases,
            SUM(total_ventas)   AS suma_ventas,
            SUM(monto_cierre)   AS suma_contado,
            SUM(diferencia)     AS diferencia_total,
            SUM(CASE WHEN diferencia > 0 THEN diferencia ELSE 0 END) AS total_sobrante,
            SUM(CASE WHEN diferencia < 0 THEN diferencia ELSE 0 END) AS total_faltante
        FROM sesiones_caja
        WHERE cierre IS NOT NULL
          AND date(apertura) BETWEEN ? AND ?
    """, params).fetchone()

    sesiones = conn.execute("""
        SELECT s.id, s.apertura, s.cierre, u.usuario AS cajero,
               s.monto_base, s.total_ventas, s.monto_cierre, s.diferencia
        FROM sesiones_caja s
        JOIN usuarios u ON s.usuario_id = u.id
        WHERE s.cierre IS NOT NULL
          AND date(s.apertura) BETWEEN ? AND ?
        ORDER BY s.apertura DESC
    """, params).fetchall()

    conn.close()
    return {
        "periodo":  {"inicio": fecha_inicio, "fin": fecha_fin},
        "totales":  dict(totales),
        "sesiones": [dict(s) for s in sesiones],
    }


# ════════════════════════════════════════════════════════════
# KPIs GENERALES
# ════════════════════════════════════════════════════════════

@requiere_admin
def kpis_generales(fecha_inicio: str, fecha_fin: str) -> dict:
    """
    Panel de indicadores clave para el período indicado.
    Incluye comparación con el período anterior de igual duración.
    """
    from datetime import datetime, timedelta

    fmt   = "%Y-%m-%d"
    ini   = datetime.strptime(fecha_inicio, fmt)
    fin   = datetime.strptime(fecha_fin,   fmt)
    delta = fin - ini

    # Período anterior de igual duración
    ini_ant = (ini - delta - timedelta(days=1)).strftime(fmt)
    fin_ant = (ini - timedelta(days=1)).strftime(fmt)

    conn = get_connection()

    def _totales(fi, ff):
        return conn.execute("""
            SELECT
                COUNT(*)        AS num_ventas,
                COALESCE(SUM(total), 0) AS ingresos,
                COALESCE(AVG(total), 0) AS ticket_promedio
            FROM ventas
            WHERE date(fecha) BETWEEN ? AND ?
        """, (fi, ff)).fetchone()

    actual   = dict(_totales(fecha_inicio, fecha_fin))
    anterior = dict(_totales(ini_ant, fin_ant))

    def _variacion(actual, anterior):
        if anterior == 0:
            return None
        return round(((actual - anterior) / anterior) * 100, 1)

    # Producto estrella del período
    estrella = conn.execute("""
        SELECT p.nombre, SUM(dv.cantidad) AS unidades
        FROM detalle_venta dv
        JOIN ventas    v ON dv.venta_id    = v.id
        JOIN productos p ON dv.producto_id = p.id
        WHERE date(v.fecha) BETWEEN ? AND ?
          AND dv.producto_id IS NOT NULL
        GROUP BY dv.producto_id
        ORDER BY unidades DESC
        LIMIT 1
    """, (fecha_inicio, fecha_fin)).fetchone()

    # Día con más ventas
    mejor_dia = conn.execute("""
        SELECT date(fecha) AS dia, SUM(total) AS total
        FROM ventas
        WHERE date(fecha) BETWEEN ? AND ?
        GROUP BY dia
        ORDER BY total DESC
        LIMIT 1
    """, (fecha_inicio, fecha_fin)).fetchone()

    # Ingreso por línea de negocio
    por_tipo = conn.execute("""
        SELECT tipo, SUM(total) AS total
        FROM ventas
        WHERE date(fecha) BETWEEN ? AND ?
        GROUP BY tipo
    """, (fecha_inicio, fecha_fin)).fetchall()

    conn.close()

    ingresos_tienda = next((r["total"] for r in por_tipo if r["tipo"] == "tienda"), 0)
    ingresos_cocina = next((r["total"] for r in por_tipo if r["tipo"] == "cocina"), 0)

    return {
        "periodo": {"inicio": fecha_inicio, "fin": fecha_fin},
        "ingresos": {
            "actual":    actual["ingresos"],
            "anterior":  anterior["ingresos"],
            "variacion": _variacion(actual["ingresos"], anterior["ingresos"]),
        },
        "num_ventas": {
            "actual":    actual["num_ventas"],
            "anterior":  anterior["num_ventas"],
            "variacion": _variacion(actual["num_ventas"], anterior["num_ventas"]),
        },
        "ticket_promedio": {
            "actual":    round(actual["ticket_promedio"], 0),
            "anterior":  round(anterior["ticket_promedio"], 0),
            "variacion": _variacion(actual["ticket_promedio"], anterior["ticket_promedio"]),
        },
        "por_linea": {
            "tienda": ingresos_tienda,
            "cocina": ingresos_cocina,
        },
        "producto_estrella": dict(estrella) if estrella else None,
        "mejor_dia":         dict(mejor_dia) if mejor_dia else None,
    }


# ════════════════════════════════════════════════════════════
# EXPORTAR A EXCEL
# ════════════════════════════════════════════════════════════

@requiere_admin
def exportar_ventas_excel(
    fecha_inicio: str,
    fecha_fin: str,
    ruta: str = "ventas_export.xlsx"
) -> str:
    """
    Exporta las ventas del período a un archivo Excel (.xlsx).
    Genera tres hojas: Ventas, Detalle y Resumen.
    Retorna la ruta del archivo generado.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    # ── Colores ──────────────────────────────────────────────
    COLOR_HEADER   = "1B4F8A"   # azul oscuro
    COLOR_HEADER2  = "2E86DE"   # azul medio
    COLOR_SUBTOTAL = "EBF3FB"   # azul muy claro
    COLOR_TIENDA   = "E8F5EE"   # verde claro
    COLOR_COCINA   = "FEF3E2"   # naranja claro
    BLANCO         = "FFFFFF"

    def estilo_header(celda, color=COLOR_HEADER):
        celda.font      = Font(bold=True, color=BLANCO, size=10)
        celda.fill      = PatternFill("solid", fgColor=color)
        celda.alignment = Alignment(horizontal="center", vertical="center")
        celda.border    = Border(
            bottom=Side(style="thin", color="CCCCCC"),
            right=Side(style="thin",  color="CCCCCC"),
        )

    def estilo_dato(celda, negrita=False, alineacion="left", fondo=None):
        celda.font      = Font(bold=negrita, size=9)
        celda.alignment = Alignment(horizontal=alineacion, vertical="center")
        if fondo:
            celda.fill = PatternFill("solid", fgColor=fondo)

    def autoajustar(hoja, min_ancho=10, max_ancho=50):
        for col in hoja.columns:
            ancho = min_ancho
            for celda in col:
                if celda.value:
                    ancho = max(ancho, min(len(str(celda.value)) + 2, max_ancho))
            hoja.column_dimensions[get_column_letter(col[0].column)].width = ancho

    conn = get_connection()

    # ── Datos ─────────────────────────────────────────────────
    ventas = conn.execute("""
        SELECT v.id, v.fecha, v.tipo, v.metodo_pago,
               v.total, v.descuento, u.usuario AS vendedor, v.notas
        FROM ventas v
        JOIN usuarios u ON v.usuario_id = u.id
        WHERE date(v.fecha) BETWEEN ? AND ?
        ORDER BY v.fecha, v.id
    """, (fecha_inicio, fecha_fin)).fetchall()

    detalle = conn.execute("""
        SELECT
            v.id AS venta_id, v.fecha, v.tipo,
            COALESCE(p.nombre, cb.nombre, 'Combo') AS producto,
            COALESCE(c.nombre, 'Combo')             AS categoria,
            dv.cantidad, dv.precio_unit, dv.subtotal
        FROM detalle_venta dv
        JOIN ventas v      ON dv.venta_id    = v.id
        LEFT JOIN productos p  ON dv.producto_id = p.id
        LEFT JOIN categorias c ON p.categoria_id = c.id
        LEFT JOIN combos cb    ON dv.combo_id    = cb.id
        WHERE date(v.fecha) BETWEEN ? AND ?
        ORDER BY v.fecha, v.id
    """, (fecha_inicio, fecha_fin)).fetchall()

    por_dia = conn.execute("""
        SELECT date(fecha) AS dia,
               COUNT(*)      AS num_ventas,
               SUM(total)    AS total,
               SUM(CASE WHEN tipo='tienda' THEN total ELSE 0 END) AS tienda,
               SUM(CASE WHEN tipo='cocina' THEN total ELSE 0 END) AS cocina
        FROM ventas
        WHERE date(fecha) BETWEEN ? AND ?
        GROUP BY dia ORDER BY dia
    """, (fecha_inicio, fecha_fin)).fetchall()

    por_metodo = conn.execute("""
        SELECT metodo_pago, COUNT(*) AS num, SUM(total) AS total
        FROM ventas
        WHERE date(fecha) BETWEEN ? AND ?
        GROUP BY metodo_pago ORDER BY total DESC
    """, (fecha_inicio, fecha_fin)).fetchall()

    top_productos = conn.execute("""
        SELECT COALESCE(p.nombre, cb.nombre) AS nombre,
               SUM(dv.cantidad)  AS unidades,
               SUM(dv.subtotal)  AS ingresos
        FROM detalle_venta dv
        JOIN ventas v ON dv.venta_id = v.id
        LEFT JOIN productos p ON dv.producto_id = p.id
        LEFT JOIN combos cb   ON dv.combo_id    = cb.id
        WHERE date(v.fecha) BETWEEN ? AND ?
        GROUP BY COALESCE(p.nombre, cb.nombre)
        ORDER BY ingresos DESC LIMIT 10
    """, (fecha_inicio, fecha_fin)).fetchall()

    conn.close()

    wb = Workbook()

    # ══════════════════════════════════════════
    # HOJA 1 — Ventas
    # ══════════════════════════════════════════
    ws1 = wb.active
    ws1.title = "Ventas"
    ws1.row_dimensions[1].height = 20
    ws1.freeze_panes = "A2"

    hdrs1 = ["ID", "Fecha", "Tipo", "Método Pago", "Total ($)", "Descuento ($)", "Vendedor", "Notas"]
    for col, h in enumerate(hdrs1, 1):
        c = ws1.cell(row=1, column=col, value=h)
        estilo_header(c)

    for fila_n, v in enumerate(ventas, 2):
        fondo = COLOR_TIENDA if v["tipo"] == "tienda" else COLOR_COCINA
        datos = [v["id"], v["fecha"][:16], v["tipo"], v["metodo_pago"],
                 v["total"], v["descuento"] or 0, v["vendedor"], v["notas"] or ""]
        for col, val in enumerate(datos, 1):
            c = ws1.cell(row=fila_n, column=col, value=val)
            alin = "right" if col in (1, 5, 6) else "left"
            estilo_dato(c, alineacion=alin, fondo=fondo if col > 1 else None)

    # Fila de totales
    fila_tot = len(ventas) + 2
    ws1.cell(row=fila_tot, column=4, value="TOTAL").font = Font(bold=True, size=9)
    c_tot = ws1.cell(row=fila_tot, column=5, value=sum(v["total"] for v in ventas))
    c_tot.font      = Font(bold=True, size=9)
    c_tot.fill      = PatternFill("solid", fgColor=COLOR_SUBTOTAL)
    c_tot.alignment = Alignment(horizontal="right")

    autoajustar(ws1)

    # ══════════════════════════════════════════
    # HOJA 2 — Detalle por ítem
    # ══════════════════════════════════════════
    ws2 = wb.create_sheet("Detalle")
    ws2.freeze_panes = "A2"

    hdrs2 = ["Venta ID", "Fecha", "Tipo", "Producto / Combo", "Categoría",
             "Cantidad", "Precio Unit ($)", "Subtotal ($)"]
    for col, h in enumerate(hdrs2, 1):
        estilo_header(ws2.cell(row=1, column=col, value=h), COLOR_HEADER2)

    for fila_n, d in enumerate(detalle, 2):
        fondo = COLOR_TIENDA if d["tipo"] == "tienda" else COLOR_COCINA
        datos = [d["venta_id"], d["fecha"][:16], d["tipo"], d["producto"],
                 d["categoria"], d["cantidad"], d["precio_unit"], d["subtotal"]]
        for col, val in enumerate(datos, 1):
            alin = "right" if col in (1, 6, 7, 8) else "left"
            estilo_dato(ws2.cell(row=fila_n, column=col, value=val),
                        alineacion=alin, fondo=fondo if col > 2 else None)

    autoajustar(ws2)

    # ══════════════════════════════════════════
    # HOJA 3 — Resumen
    # ══════════════════════════════════════════
    ws3 = wb.create_sheet("Resumen")
    fila = 1

    def seccion(titulo, color=COLOR_HEADER):
        nonlocal fila
        c = ws3.cell(row=fila, column=1, value=titulo)
        c.font      = Font(bold=True, color=BLANCO, size=10)
        c.fill      = PatternFill("solid", fgColor=color)
        c.alignment = Alignment(horizontal="left", vertical="center")
        ws3.row_dimensions[fila].height = 18
        fila += 1

    def dato_res(label, valor, negrita=False, fondo=None):
        nonlocal fila
        c1 = ws3.cell(row=fila, column=1, value=label)
        c2 = ws3.cell(row=fila, column=2, value=valor)
        c1.font = Font(bold=negrita, size=9)
        c2.font = Font(bold=negrita, size=9)
        c2.alignment = Alignment(horizontal="right")
        if fondo:
            c1.fill = PatternFill("solid", fgColor=fondo)
            c2.fill = PatternFill("solid", fgColor=fondo)
        fila += 1

    # Período
    seccion(f"Período: {fecha_inicio}  →  {fecha_fin}")
    total_general = sum(v["total"] for v in ventas)
    tienda_total  = sum(v["total"] for v in ventas if v["tipo"] == "tienda")
    cocina_total  = sum(v["total"] for v in ventas if v["tipo"] == "cocina")
    dato_res("Total de ventas (transacciones)", len(ventas))
    dato_res("Ingresos totales ($)",            total_general, negrita=True, fondo=COLOR_SUBTOTAL)
    dato_res("Ingresos tienda ($)",             tienda_total,  fondo=COLOR_TIENDA)
    dato_res("Ingresos cocina ($)",             cocina_total,  fondo=COLOR_COCINA)
    dato_res("Ticket promedio ($)",
             round(total_general / len(ventas), 0) if ventas else 0)
    fila += 1

    # Por día
    seccion("Ventas por día", COLOR_HEADER2)
    dato_res("Día", "Total ($)", negrita=True)
    for d in por_dia:
        dato_res(d["dia"], d["total"])
    fila += 1

    # Por método de pago
    seccion("Por método de pago", COLOR_HEADER2)
    dato_res("Método", "Total ($)", negrita=True)
    for m in por_metodo:
        dato_res(m["metodo_pago"], m["total"])
    fila += 1

    # Top productos
    seccion("Top 10 productos más vendidos", COLOR_HEADER2)
    ws3.cell(row=fila, column=1, value="Producto").font = Font(bold=True, size=9)
    ws3.cell(row=fila, column=2, value="Unidades").font = Font(bold=True, size=9)
    ws3.cell(row=fila, column=3, value="Ingresos ($)").font = Font(bold=True, size=9)
    fila += 1
    for p in top_productos:
        ws3.cell(row=fila, column=1, value=p["nombre"]).font = Font(size=9)
        ws3.cell(row=fila, column=2, value=p["unidades"]).font = Font(size=9)
        ws3.cell(row=fila, column=3, value=p["ingresos"]).font = Font(size=9)
        ws3.cell(row=fila, column=3).alignment = Alignment(horizontal="right")
        fila += 1

    ws3.column_dimensions["A"].width = 35
    ws3.column_dimensions["B"].width = 18
    ws3.column_dimensions["C"].width = 18

    wb.save(ruta)
    return ruta


# Alias para compatibilidad con código anterior
@requiere_admin
def exportar_ventas_csv(fecha_inicio: str, fecha_fin: str,
                         ruta: str = "ventas_export.csv") -> str:
    """Alias — redirige a exportar_ventas_excel cambiando la extensión."""
    ruta_xlsx = ruta.replace(".csv", ".xlsx") if ruta.endswith(".csv") else ruta + ".xlsx"
    return exportar_ventas_excel(fecha_inicio, fecha_fin, ruta_xlsx)


# ════════════════════════════════════════════════════════════
# PRUEBA DIRECTA
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from database import inicializar
    from auth import iniciar_sesion
    from modules.inventario import (
        crear_producto, crear_insumo, guardar_receta, listar_categorias
    )
    from modules.ventas import Carrito, registrar_venta, crear_combo
    from modules.caja import abrir_caja, formatear_pesos
    from datetime import date

    inicializar()
    iniciar_sesion("admin", "admin123")

    # Preparar datos de prueba
    cats       = {c["nombre"]: c["id"] for c in listar_categorias()}
    id_sobre   = crear_producto("Sobre TCG", cats["TCG - Sobres"],
                                 precio_venta=15000, precio_costo=9000, stock=30)
    id_juego   = crear_producto("Catan", cats["Juegos de mesa"],
                                 precio_venta=85000, precio_costo=50000, stock=5)
    id_ham     = crear_producto("Hamburguesa", cats["Comidas rápidas"],
                                 precio_venta=12000, precio_costo=5500, stock=0)
    id_gaseosa = crear_producto("Gaseosa", cats["Bebidas"],
                                 precio_venta=3000, precio_costo=1200, stock=0)

    id_carne = crear_insumo("Carne", stock=30, unidad="porción")
    id_pan   = crear_insumo("Pan",   stock=30, unidad="unidad")
    guardar_receta(id_ham, [
        {"insumo_id": id_carne, "cantidad": 1},
        {"insumo_id": id_pan,   "cantidad": 1},
    ])
    id_combo = crear_combo("Combo 1", precio=13500, productos=[
        {"producto_id": id_ham,     "cantidad": 1},
        {"producto_id": id_gaseosa, "cantidad": 1},
    ])

    # Registrar ventas de prueba
    sesion_id = abrir_caja(50000)
    for _ in range(3):
        c = Carrito()
        c.agregar_producto(id_sobre, 2)
        registrar_venta(c, "efectivo", sesion_id=sesion_id)
    for _ in range(2):
        c = Carrito()
        c.agregar_combo(id_combo, 1)
        registrar_venta(c, "nequi", sesion_id=sesion_id)
    c = Carrito()
    c.agregar_producto(id_juego, 1)
    registrar_venta(c, "transferencia", sesion_id=sesion_id)

    hoy = date.today().isoformat()

    print("\n── KPIs generales ──")
    kpis = kpis_generales(hoy, hoy)
    print(f"  Ingresos:        {formatear_pesos(kpis['ingresos']['actual'])}")
    print(f"  Ventas:          {kpis['num_ventas']['actual']}")
    print(f"  Ticket promedio: {formatear_pesos(kpis['ticket_promedio']['actual'])}")
    print(f"  Tienda:          {formatear_pesos(kpis['por_linea']['tienda'])}")
    print(f"  Cocina:          {formatear_pesos(kpis['por_linea']['cocina'])}")
    if kpis["producto_estrella"]:
        print(f"  Producto estrella: {kpis['producto_estrella']['nombre']} ({kpis['producto_estrella']['unidades']} uds)")

    print("\n── Productos más vendidos ──")
    for p in productos_mas_vendidos(hoy, hoy):
        print(f"  {p['nombre']}: {p['unidades_vendidas']} uds — {formatear_pesos(p['ingresos_totales'])}")

    print("\n── Reporte de inventario ──")
    inv = reporte_inventario()
    print(f"  Productos activos:   {inv['totales']['total_productos']}")
    print(f"  Valor en costo:      {formatear_pesos(inv['totales']['valor_costo'] or 0)}")
    print(f"  Valor en venta:      {formatear_pesos(inv['totales']['valor_venta'] or 0)}")
    print(f"  Bajo mínimo:         {len(inv['bajo_minimo'])}")

    print("\n── Exportar CSV ──")
    ruta = exportar_ventas_csv(hoy, hoy, "/tmp/ventas_test.csv")
    print(f"  Archivo generado: {ruta}")
    import os
    print(f"  Tamaño: {os.path.getsize(ruta)} bytes")