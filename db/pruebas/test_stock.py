"""Stock de productos de tienda movido por ventas, compras y premios (0015, 0021)."""

from ayudas import falla


def _stock(db, producto):
    return db.execute("SELECT stock FROM productos WHERE articulo_id = %s", (producto,)).fetchone()["stock"]


def test_vender_descuenta_sin_quedar_negativo(db, f):
    s, prod = f.turno(), f.producto(precio=1000, stock=3)
    f.venta(s, [(prod, 3, 1000)], pagos=[("efectivo", 3000)])
    assert _stock(db, prod) == 0
    with falla(db, r"No hay stock suficiente de Prod \S+ \(hay 0, se necesitan 1\)"):
        f.venta(s, [(prod, 1, 1000)], pagos=[("efectivo", 1000)])


def test_stock_negativo_de_antes_no_se_sigue_vendiendo(db, f):
    s, prod = f.turno(), f.producto(precio=1000, stock=-2)
    with falla(db, r"hay 0, se necesitan 1"):
        f.venta(s, [(prod, 1, 1000)], pagos=[("efectivo", 1000)])


def test_cocina_no_mueve_stock(db, f):
    s, plato = f.turno(), f.producto(precio=1000, impuesto="INC8", tipo_categoria="cocina", stock=0)
    f.venta(s, [(plato, 2, 1000)], pagos=[("efectivo", 2000)])
    assert _stock(db, plato) == 0


def test_vender_un_combo_descuenta_sus_productos(db, f):
    s = f.turno()
    gaseosa, papas = f.producto(stock=7), f.producto(stock=3)
    combo = db.execute(
        "INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta) "
        "VALUES ('combo', 'Combo prueba', %s, %s, 5000) RETURNING id",
        (f.categoria("cocina"), f.impuesto("INC8"))).fetchone()["id"]
    db.execute("INSERT INTO combos (articulo_id) VALUES (%s)", (combo,))
    db.execute("INSERT INTO combo_productos VALUES (%s, %s, 2), (%s, %s, 1)", (combo, gaseosa, combo, papas))
    f.venta(s, [(combo, 3, 5000)], pagos=[("efectivo", 15000)])
    assert (_stock(db, gaseosa), _stock(db, papas)) == (1, 0)
    # Un combo más ya no alcanza: falla con lo que falta, no con el combo.
    with falla(db, r"(?=.*hay 1, se necesitan 2\))(?=.*hay 0, se necesitan 1\))"):
        f.venta(s, [(combo, 1, 5000)], pagos=[("efectivo", 5000)])


def test_compras_suman_y_editar_o_borrar_revierte(db, f):
    prov, prod, ins = f.proveedor(), f.producto(stock=0), f.insumo()
    compra = f.compra(prov, [(prod, None, 10, 1000), (None, ins, 500, 2)])
    assert _stock(db, prod) == 10
    db.execute("UPDATE compra_lineas SET cantidad = 4 WHERE compra_id = %s AND producto_id = %s", (compra, prod))
    assert _stock(db, prod) == 4
    db.execute("DELETE FROM compra_lineas WHERE compra_id = %s AND producto_id = %s", (compra, prod))
    assert _stock(db, prod) == 0


def test_premios_de_torneo_descuentan(db, f):
    s, sobre = f.turno(), f.producto(precio=5000, stock=4)
    venta = f.venta(s, [(f.inscripcion(), 1, 15000)], pagos=[("efectivo", 15000)])
    torneo = db.execute(
        "INSERT INTO torneos (nombre, juego_id, usuario_id, venta_id) "
        "SELECT 'Liga', id, %s, %s FROM juegos LIMIT 1 RETURNING id", (f.usuario(), venta)).fetchone()["id"]
    db.execute("INSERT INTO torneo_premios VALUES (%s, %s, 4, 3000)", (torneo, sobre))
    assert _stock(db, sobre) == 0
    db.execute("DELETE FROM torneo_premios WHERE torneo_id = %s", (torneo,))
    assert _stock(db, sobre) == 4
    with falla(db, r"hay 4, se necesitan 5"):
        db.execute("INSERT INTO torneo_premios VALUES (%s, %s, 5, 3000)", (torneo, sobre))


def test_ventas_siguen_sin_editarse(db, f):
    s, prod = f.turno(), f.producto(precio=1000)
    v = f.venta(s, [(prod, 1, 1000)], pagos=[("efectivo", 1000)])
    with falla(db, "solo inserción"):
        db.execute("UPDATE detalle_venta SET cantidad = 5 WHERE venta_id = %s", (v,))


def test_una_venta_de_varias_lineas_en_un_solo_insert(db, f):
    # Así inserta la API: todas las líneas juntas, el combo y sus productos sueltos.
    s = f.turno()
    gaseosa, papas = f.producto(stock=3), f.producto(stock=0)
    combo = db.execute(
        "INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta) "
        "VALUES ('combo', 'Combo dos', %s, %s, 5000) RETURNING id",
        (f.categoria("cocina"), f.impuesto("INC8"))).fetchone()["id"]
    db.execute("INSERT INTO combos (articulo_id) VALUES (%s)", (combo,))
    db.execute("INSERT INTO combo_productos VALUES (%s, %s, 1)", (combo, gaseosa))
    v = f.venta(s, [], pagos=[("efectivo", 7000)])
    db.execute(
        "INSERT INTO detalle_venta (venta_id, articulo_id, cantidad, precio_unit, impuesto_id) "
        "SELECT %s, a.id, x.cantidad, x.precio, a.impuesto_id "
        "  FROM (VALUES (%s::uuid, 1, 5000), (%s::uuid, 2, 1000)) x(articulo, cantidad, precio) "
        "  JOIN articulos a ON a.id = x.articulo",
        (v, combo, gaseosa))
    assert (_stock(db, gaseosa), _stock(db, papas)) == (0, 0)
