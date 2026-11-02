"""Grupos 5 y 6: cuadre de ventas, vista v_ventas y cuentas de mesa."""
from decimal import Decimal

from ayudas import confirmar, falla


def _v(db, venta):
    return db.execute("SELECT total, metodo, tipo, pagado, fiado FROM v_ventas WHERE id = %s",
                      (venta,)).fetchone()


def test_venta_mixta_con_fiado_cuadra(db, f):
    s, cliente = f.turno(), f.cliente()
    tienda = f.producto(precio=20000)
    comida = f.producto(precio=15000, tipo_categoria="cocina", impuesto="INC8")
    v = f.venta(s, [(tienda, 1, 20000), (comida, 2, 15000)], descuento=5000,
                pagos=[("efectivo", 25000)], fiado=[(cliente, 20000)], cliente_id=cliente)
    confirmar(db)
    assert _v(db, v) == {"total": Decimal("45000.00"), "metodo": "mixto", "tipo": "mixta",
                         "pagado": Decimal("25000"), "fiado": Decimal("20000")}


def test_metodo_unico_y_credito_puro(db, f):
    s, cliente, prod = f.turno(), f.cliente(), f.producto(precio=1000)
    v1 = f.venta(s, [(prod, 2, 1000)], pagos=[("transferencia", 1000), ("transferencia", 1000)])
    v2 = f.venta(s, [(prod, 1, 1000)], fiado=[(cliente, 1000)])
    confirmar(db)
    assert _v(db, v1)["metodo"] == "transferencia" and _v(db, v1)["tipo"] == "tienda"
    assert _v(db, v2)["metodo"] == "credito"


def test_venta_que_no_cuadra_no_se_confirma(db, f):
    s, prod = f.turno(), f.producto(precio=10000)
    with falla(db, "no cuadra"):
        f.venta(s, [(prod, 1, 10000)], pagos=[("efectivo", 9000)])
    with falla(db, "no cuadra"):  # las vueltas no se guardan
        f.venta(s, [(prod, 1, 10000)], pagos=[("efectivo", 20000)])
    with falla(db, "supera su subtotal"):
        f.venta(s, [(prod, 1, 10000)], descuento=12000)
    with falla(db, "no tiene líneas"):
        f.venta(s, [], pagos=[("efectivo", 1000)])


def test_ventas_solo_insercion(db, f):
    s, prod = f.turno(), f.producto(precio=1000)
    v = f.venta(s, [(prod, 1, 1000)], pagos=[("efectivo", 1000)])
    confirmar(db)
    with falla(db, "solo inserción"):
        db.execute("DELETE FROM ventas WHERE id = %s", (v,))
    with falla(db, "solo inserción"):
        db.execute("UPDATE detalle_venta SET precio_unit = 0 WHERE venta_id = %s", (v,))


# ── Mesas ───────────────────────────────────────────────────────────────────

def _cuenta(db, f, mesa="1", cliente=None, alias="Grupo"):
    return db.execute(
        "INSERT INTO cuentas (mesa_id, cliente_id, alias, abierta_por) "
        "VALUES ((SELECT id FROM mesas WHERE nombre = %s), %s, %s, %s) RETURNING id",
        (mesa, cliente, None if cliente else alias, f.usuario())).fetchone()["id"]


def test_una_cuenta_abierta_por_mesa(db, f):
    _cuenta(db, f, mesa="3")
    with falla(db, "cuentas_una_abierta_por_mesa"):
        _cuenta(db, f, mesa="3")
    _cuenta(db, f, mesa=None)
    _cuenta(db, f, mesa=None)  # sin mesa no hay límite


def test_cliente_o_alias_exactamente_uno(db, f):
    with falla(db, "cuentas_cliente_o_alias"):
        db.execute("INSERT INTO cuentas (abierta_por) VALUES (%s)", (f.usuario(),))
    with falla(db, "cuentas_cliente_o_alias"):
        db.execute("INSERT INTO cuentas (cliente_id, alias, abierta_por) VALUES (%s, 'x', %s)",
                   (f.cliente(), f.usuario()))


def test_cobrar_mueve_las_lineas_a_la_venta(db, f):
    s, prod = f.turno(), f.producto(precio=4000)
    cu = _cuenta(db, f, mesa="5")
    db.execute("INSERT INTO cuenta_items (cuenta_id, articulo_id, cantidad, precio_unit) VALUES (%s, %s, 3, 4000)",
               (cu, prod))
    assert db.execute("SELECT estado, total_items FROM v_cuentas WHERE id = %s", (cu,)).fetchone() == \
        {"estado": "abierta", "total_items": Decimal("12000.00")}
    v = f.venta(s, [(prod, 3, 4000)], pagos=[("efectivo", 12000)])
    with falla(db, "deben pasar a la venta"):
        db.execute("UPDATE cuentas SET venta_id = %s WHERE id = %s", (v, cu))
    db.execute("DELETE FROM cuenta_items WHERE cuenta_id = %s", (cu,))
    db.execute("UPDATE cuentas SET venta_id = %s WHERE id = %s", (v, cu))
    confirmar(db)
    assert db.execute("SELECT estado FROM v_cuentas WHERE id = %s", (cu,)).fetchone()["estado"] == "cobrada"
    with falla(db, "ya está cerrada"):
        db.execute("INSERT INTO cuenta_items (cuenta_id, articulo_id, cantidad, precio_unit) VALUES (%s, %s, 1, 1)",
                   (cu, prod))
    with falla(db, "ya está cerrada"):
        db.execute("UPDATE cuentas SET notas = 'x' WHERE id = %s", (cu,))
    _cuenta(db, f, mesa="5")  # la mesa quedó libre


def test_cuenta_cancelada_conserva_sus_items(db, f):
    prod = f.producto(precio=2000)
    cu = _cuenta(db, f, mesa="7")
    db.execute("INSERT INTO cuenta_items (cuenta_id, articulo_id, cantidad, precio_unit) VALUES (%s, %s, 2, 2000)",
               (cu, prod))
    db.execute("UPDATE cuentas SET cancelada_en = now() WHERE id = %s", (cu,))
    with falla(db, "ya está cerrada"):
        db.execute("DELETE FROM cuenta_items WHERE cuenta_id = %s", (cu,))
    assert db.execute("SELECT estado, total_items FROM v_cuentas WHERE id = %s", (cu,)).fetchone() == \
        {"estado": "cancelada", "total_items": Decimal("4000.00")}
