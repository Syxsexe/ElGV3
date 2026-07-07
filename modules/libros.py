"""
modules/libros.py — El G POS
Libros contables de ventas y compras.

Libro de ventas:  registro cronológico de ventas/facturas con base gravable,
                  IVA y total. Usa los datos de la factura cuando existe; para
                  ventas POS sin factura, el total se toma como base sin IVA.

Libro de compras: registro de egresos — pedidos a proveedores recibidos y
                  gastos generales.
"""

from datetime import date

from database import get_connection

IVA_POR_DEFECTO = 0.19


def libro_ventas(fecha_inicio: str = None, fecha_fin: str = None) -> list[dict]:
    """
    Retorna las ventas del rango como asientos del libro de ventas.
    Cada fila: fecha, documento, cliente, nit, base, iva, total, dian, metodo.
    """
    conn = get_connection()
    query = """
        SELECT v.id AS venta_id, v.fecha, v.total, v.metodo_pago, v.tipo,
               f.numero, f.tipo_documento, f.documento,
               f.total_base, f.iva, f.dian_status,
               c.nombre AS cliente_nombre
        FROM ventas v
        LEFT JOIN facturas f ON f.venta_id = v.id
        LEFT JOIN clientes c ON v.cliente_id = c.id
        WHERE 1=1
    """
    params = []
    if fecha_inicio:
        query += " AND date(v.fecha) >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND date(v.fecha) <= ?"
        params.append(fecha_fin)
    query += " ORDER BY v.fecha ASC, v.id ASC"

    filas = conn.execute(query, params).fetchall()
    conn.close()

    libro = []
    for r in filas:
        r = dict(r)
        if r["numero"]:                      # tiene factura
            base = r["total_base"] or 0
            iva = r["iva"] or 0
            documento = r["numero"]
        else:                                # venta POS sin factura
            base = r["total"]
            iva = 0
            documento = f"POS-{r['venta_id']}"
        libro.append({
            "fecha": r["fecha"][:16],
            "documento": documento,
            "cliente": r["cliente_nombre"] or "Consumidor Final",
            "nit": (f"{r['tipo_documento']} {r['documento']}"
                    if r["documento"] else ""),
            "base": round(base, 2),
            "iva": round(iva, 2),
            "total": round(r["total"], 2),
            "metodo": r["metodo_pago"],
            "dian": r["dian_status"] or ("—" if not r["numero"] else "local"),
        })
    return libro


def libro_compras(fecha_inicio: str = None, fecha_fin: str = None) -> list[dict]:
    """
    Retorna las compras del rango: pedidos recibidos + gastos generales.
    Cada fila: fecha, documento, tercero, concepto, base, iva, total, metodo.
    """
    from modules.proveedores import migrar_egresos
    from modules.compras import migrar as migrar_compras
    migrar_egresos()
    migrar_compras()

    conn = get_connection()
    libro = []

    # ── Facturas de compra de proveedor (con IVA discriminado) ────────────────
    q_cmp = """
        SELECT cp.id, cp.fecha, cp.numero_factura, cp.tipo_documento, cp.cufe,
               cp.base, cp.iva, cp.total, cp.metodo_pago, pr.nombre AS proveedor
        FROM compras_proveedor cp
        JOIN proveedores pr ON cp.proveedor_id = pr.id
        WHERE 1=1
    """
    params_c = []
    if fecha_inicio:
        q_cmp += " AND date(cp.fecha) >= ?"
        params_c.append(fecha_inicio)
    if fecha_fin:
        q_cmp += " AND date(cp.fecha) <= ?"
        params_c.append(fecha_fin)

    for r in conn.execute(q_cmp, params_c).fetchall():
        r = dict(r)
        etiqueta = "FE" if r["tipo_documento"] == "factura_electronica" else "FC"
        libro.append({
            "fecha": r["fecha"][:16],
            "documento": r["numero_factura"],
            "tercero": r["proveedor"],
            "concepto": f"Compra ({etiqueta})" + (f" · CUFE {r['cufe'][:12]}…" if r["cufe"] else ""),
            "base": round(r["base"], 2),
            "iva": round(r["iva"], 2),
            "total": round(r["total"], 2),
            "metodo": r["metodo_pago"] or "—",
            "tipo": "compra",
        })

    # Pedidos que ya tienen factura de compra registrada: no se listan aparte
    # (evita doble conteo). Solo los pedidos recibidos SIN factura de compra.
    # ── Pedidos a proveedores (recibidos) ─────────────────────────────────────
    q_ped = """
        SELECT p.id, p.fecha, p.total, pr.nombre AS proveedor
        FROM pedidos p
        JOIN proveedores pr ON p.proveedor_id = pr.id
        WHERE p.estado = 'recibido'
          AND NOT EXISTS (SELECT 1 FROM compras_proveedor cp WHERE cp.pedido_id = p.id)
    """
    params_p = []
    if fecha_inicio:
        q_ped += " AND date(p.fecha) >= ?"
        params_p.append(fecha_inicio)
    if fecha_fin:
        q_ped += " AND date(p.fecha) <= ?"
        params_p.append(fecha_fin)

    for r in conn.execute(q_ped, params_p).fetchall():
        r = dict(r)
        total = r["total"] or 0
        # Los pedidos no discriminan IVA; se registra el total como base.
        libro.append({
            "fecha": r["fecha"][:16],
            "documento": f"PED-{r['id']}",
            "tercero": r["proveedor"],
            "concepto": "Compra de inventario/insumos",
            "base": round(total, 2),
            "iva": 0.0,
            "total": round(total, 2),
            "metodo": "—",
            "tipo": "pedido",
        })

    # ── Gastos generales (egresos sin pedido) ─────────────────────────────────
    q_gas = """
        SELECT e.id, e.fecha, e.concepto, e.categoria, e.total, e.metodo_pago
        FROM egresos e
        WHERE e.pedido_id IS NULL
    """
    params_g = []
    if fecha_inicio:
        q_gas += " AND date(e.fecha) >= ?"
        params_g.append(fecha_inicio)
    if fecha_fin:
        q_gas += " AND date(e.fecha) <= ?"
        params_g.append(fecha_fin)

    for r in conn.execute(q_gas, params_g).fetchall():
        r = dict(r)
        total = r["total"] or 0
        libro.append({
            "fecha": r["fecha"][:16],
            "documento": f"GAS-{r['id']}",
            "tercero": r["categoria"] or "Gasto",
            "concepto": r["concepto"],
            "base": round(total, 2),
            "iva": 0.0,
            "total": round(total, 2),
            "metodo": r["metodo_pago"] or "efectivo",
            "tipo": "gasto",
        })

    conn.close()
    libro.sort(key=lambda x: x["fecha"])
    return libro


def totales(libro: list[dict]) -> dict:
    """Suma base, IVA y total de un libro."""
    return {
        "base": round(sum(f["base"] for f in libro), 2),
        "iva": round(sum(f["iva"] for f in libro), 2),
        "total": round(sum(f["total"] for f in libro), 2),
        "registros": len(libro),
    }


def exportar_csv(libro: list[dict], ruta: str, columnas: list[str]) -> str:
    """Exporta un libro a CSV con las columnas indicadas (en orden)."""
    import csv
    with open(ruta, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=columnas, extrasaction="ignore")
        writer.writeheader()
        for fila in libro:
            writer.writerow(fila)
    return ruta
