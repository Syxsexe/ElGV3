"""Inicio y reportes. Los reportes usan movimientos fechados en marzo de 2001,
que ninguna otra prueba toca, para poder comparar cifras exactas."""
import datetime


def _venta(bd, f, turno, dia, lineas, pagos=(), fiado=None, descuento=0):
    """lineas = [(articulo_id, cantidad, precio, costo)]; fiado = (cliente, monto)."""
    usuario = f.usuario()
    vid = bd.execute(
        "INSERT INTO ventas (sesion_id, usuario_id, descuento, creada_en, cliente_id) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (turno, usuario, descuento, dia, fiado[0] if fiado else None)).fetchone()["id"]
    for articulo, cantidad, precio, costo in lineas:
        bd.execute("""INSERT INTO detalle_venta (venta_id, articulo_id, cantidad, precio_unit, costo_unit, impuesto_id)
                      SELECT %s, id, %s, %s, %s, impuesto_id FROM articulos WHERE id = %s""",
                   (vid, cantidad, precio, costo, articulo))
    for codigo, monto in pagos:
        f.pago_venta(vid, codigo, monto)
    if fiado:
        f.cargo(fiado[0], fiado[1], venta_id=vid)
    return vid


def _egreso(bd, f, turno, dia, monto, *, categoria=None, compra_id=None):
    eid = bd.execute(
        """INSERT INTO egresos (sesion_id, usuario_id, categoria_gasto_id, compra_id, concepto, creado_en)
           VALUES (%s, %s, %s, %s, 'x', %s) RETURNING id""",
        (turno, f.usuario(), f.id_de("categorias_gasto", "nombre", categoria) if categoria else None, compra_id, dia)).fetchone()["id"]
    f.pago_egreso(eid, "efectivo", monto)
    return eid


def test_reporte_por_rango(api, sesion, bd, f, turno):
    d1, d2, d3 = (datetime.datetime(2001, 3, n, 12, tzinfo=datetime.timezone(datetime.timedelta(hours=-5))) for n in (1, 2, 3))
    with bd.transaction():
        tienda, cocina = f.producto(), f.producto(tipo_categoria="cocina")
        cliente = f.cliente()
    with bd.transaction():
        _venta(bd, f, turno, d1, [(tienda, 2, 10000, 4000)], pagos=[("efectivo", 20000)])
        _venta(bd, f, turno, d2, [(cocina, 1, 15000, 5000)], pagos=[("nequi", 10000)], fiado=(cliente, 4000), descuento=1000)
    with bd.transaction():
        _egreso(bd, f, turno, d2, 3000, categoria="Otros")
        anulado = _egreso(bd, f, turno, d2, 2000, categoria="Otros")
        bd.execute("INSERT INTO anulaciones_egreso (egreso_id, sesion_id, usuario_id, motivo) VALUES (%s, %s, %s, 'x')",
                   (anulado, turno, f.usuario()))
    with bd.transaction():
        compra = f.compra(f.proveedor(), [(tienda, None, 1, 1000)])
        _egreso(bd, f, turno, d2, 1000, compra_id=compra)  # pago de compra: no es gasto
    with bd.transaction():  # se perdona parte del fiado: esa plata no llega
        cargo = bd.execute("SELECT id FROM cargos_credito WHERE cliente_id = %s", (cliente,)).fetchone()["id"]
        bd.execute("""INSERT INTO condonaciones_credito (cargo_id, monto, motivo, autorizada_por, creado_en)
                      VALUES (%s, 1000, 'Cliente frecuente', %s, %s)""", (cargo, f.usuario(), d2))
    with bd.transaction():
        torneo = bd.execute("""INSERT INTO torneos (nombre, juego_id, realizado_en, usuario_id)
                               SELECT 'Torneo del reporte 2001', id, %s, %s FROM juegos LIMIT 1 RETURNING id""", (d3, f.usuario())).fetchone()["id"]
        bd.execute("INSERT INTO torneo_premios (torneo_id, producto_id, cantidad, costo_unit) VALUES (%s, %s, 1, 2000)",
                   (torneo, tienda))

    h = sesion("admin")
    r = api.get("/reportes", headers=h, params={"desde": "2001-03-01", "hasta": "2001-03-03"})
    assert r.status_code == 200, r.text
    rep = r.json()
    res = rep["resumen"]
    assert (res["cantidad"], res["subtotal"], res["descuentos"], res["total"], res["fiado"]) == (2, 35000, 1000, 34000, 4000)
    assert (res["costo"], res["utilidad_bruta"], res["margen"]) == (13000, 21000, 61.8)
    assert (res["gastos"], res["premios"], res["condonado"], res["resultado"]) == (3000, 2000, 1000, 15000)
    assert [(d["dia"], d["ventas"], d["cantidad"], d["gastos"]) for d in rep["por_dia"]] == \
        [("2001-03-01", 20000, 1, 0), ("2001-03-02", 14000, 1, 3000), ("2001-03-03", 0, 0, 0)]
    assert sorted((c["tipo"], c["ventas"], c["costo"]) for c in rep["por_categoria"]) == [("cocina", 15000, 5000), ("tienda", 20000, 8000)]
    assert rep["por_categoria"][0]["ventas"] == 20000  # de mayor a menor
    assert [(m["metodo"], m["monto"]) for m in rep["por_metodo"]] == [("Efectivo", 20000), ("Nequi", 10000), ("Fiado", 4000)]
    assert [(g["categoria"], g["monto"]) for g in rep["gastos_por_categoria"]] == [("Otros", 3000)]
    assert (rep["torneos"]["cantidad"], rep["torneos"]["premios"]) == (1, 2000)
    assert [p["unidades"] for p in rep["productos"]] == [2, 1]

    # Un rango sin movimientos.
    vacio = api.get("/reportes", headers=h, params={"desde": "2001-04-01", "hasta": "2001-04-01"}).json()
    assert (vacio["resumen"]["total"], vacio["resumen"]["margen"], len(vacio["por_dia"])) == (0, None, 1)


def test_reporte_rechazado(api, sesion):
    admin = sesion("admin")
    r = api.get("/reportes", headers=admin, params={"desde": "2001-03-05", "hasta": "2001-03-01"})
    assert (r.status_code, r.json()["detail"]) == (400, "La fecha final es anterior a la inicial.")
    r = api.get("/reportes", headers=admin, params={"desde": "2000-01-01", "hasta": "2001-12-31"})
    assert r.status_code == 400 and "rango máximo" in r.json()["detail"]
    assert api.get("/reportes", headers=sesion("vendedor"), params={"desde": "2001-03-01", "hasta": "2001-03-01"}).status_code == 403
    assert api.get("/reportes", headers=admin).status_code == 422


def test_inicio(api, sesion, bd, f, turno):
    with bd.transaction():
        pocas = f.producto()
    bd.execute("UPDATE productos SET stock = 1, stock_minimo = 5 WHERE articulo_id = %s", (pocas,))
    moroso = f.cliente()
    f.cargo(moroso, 7000, notas="Viejo", vence_en="2020-01-01")

    vendedor = api.get("/inicio", headers=sesion("vendedor")).json()
    assert vendedor["turno"]["id"] == str(turno) and {"caja", "esperado"} <= set(vendedor["turno"]["cajas"][0])
    assert str(pocas) in [p["id"] for p in vendedor["bajo_minimo"]["productos"]]
    assert vendedor["bajo_minimo"]["total"] >= 1
    assert vendedor["cartera_vencida"]["total"] >= 7000 and vendedor["cartera_vencida"]["clientes"] >= 1
    assert {"ventas", "total", "tienda", "cocina"} <= set(vendedor["hoy"])
    assert {"abiertas", "total"} <= set(vendedor["cuentas"])
    assert vendedor["por_pagar"] is None  # sin compras.registrar
    admin = api.get("/inicio", headers=sesion("admin")).json()
    assert {"total", "compras"} <= set(admin["por_pagar"])
    assert api.get("/inicio").status_code == 401
