"""Combos con grupos de elección (0024): stock, costo, cuántos alcanzan y bloqueos."""
import uuid

from ayudas import confirmar, falla


def _stock(db, producto):
    return db.execute("SELECT stock FROM productos WHERE articulo_id = %s", (producto,)).fetchone()["stock"]


def _combo(db, f, precio=12000, fijos=(), grupos=()):
    """fijos = [(producto, cantidad)]; grupos = [(nombre, cantidad, [(producto, recargo)])]."""
    combo = db.execute(
        "INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta) "
        "VALUES ('combo', %s, %s, %s, %s) RETURNING id",
        (f"Combo {uuid.uuid4().hex[:6]}", f.categoria("cocina"), f.impuesto("INC8"), precio)).fetchone()["id"]
    db.execute("INSERT INTO combos (articulo_id) VALUES (%s)", (combo,))
    for producto, cantidad in fijos:
        db.execute("INSERT INTO combo_productos VALUES (%s, %s, %s)", (combo, producto, cantidad))
    for orden, (nombre, cantidad, opciones) in enumerate(grupos):
        grupo = db.execute("INSERT INTO combo_grupos (combo_id, nombre, cantidad, orden) VALUES (%s, %s, %s, %s) RETURNING id",
                           (combo, nombre, cantidad, orden)).fetchone()["id"]
        for producto, recargo in opciones:
            db.execute("INSERT INTO combo_opciones VALUES (%s, %s, %s)", (grupo, producto, recargo))
    return combo


def _vender_combo(db, f, sesion, combo, cantidad, precio, elecciones):
    """Como la API: lo elegido primero (con el id de la línea) y después la línea."""
    venta = db.execute("INSERT INTO ventas (sesion_id, usuario_id) VALUES (%s, %s) RETURNING id",
                       (sesion, f.usuario())).fetchone()["id"]
    linea = uuid.uuid4()
    for grupo, producto, cant, recargo in elecciones:
        db.execute("INSERT INTO detalle_venta_elecciones VALUES (%s, %s, %s, %s, %s)", (linea, grupo, producto, cant, recargo))
    db.execute("INSERT INTO detalle_venta (id, venta_id, articulo_id, cantidad, precio_unit, impuesto_id) "
               "SELECT %s, %s, id, %s, %s, impuesto_id FROM articulos WHERE id = %s",
               (linea, venta, cantidad, precio, combo))
    f.pago_venta(venta, "efectivo", cantidad * precio)
    return linea


def _articulo(db, combo):
    return db.execute("SELECT * FROM v_articulos WHERE id = %s", (combo,)).fetchone()


def test_vender_descuenta_lo_elegido_y_los_fijos(db, f):
    s = f.turno()
    papas, coca, pepsi = f.producto(stock=10), f.producto(stock=5), f.producto(stock=5)
    combo = _combo(db, f, fijos=[(papas, 1)], grupos=[("Bebida", 2, [(coca, 0), (pepsi, 500)])])
    _vender_combo(db, f, s, combo, 2, 12500, [("Bebida", pepsi, 2, 500)])
    confirmar(db)
    assert (_stock(db, papas), _stock(db, coca), _stock(db, pepsi)) == (8, 5, 1)
    # Lo elegido se exige como lo fijo: 2 combos con Pepsi necesitan 4 y hay 1.
    with falla(db, r"hay 1, se necesitan 4"):
        _vender_combo(db, f, s, combo, 2, 12500, [("Bebida", pepsi, 2, 500)])


def test_elegir_un_plato_abre_su_receta(db, f):
    s = f.turno()
    carne = f.insumo(costo=10)
    db.execute("UPDATE insumos SET stock = 1000 WHERE id = %s", (carne,))
    hamburguesa = f.producto(precio=15000, impuesto="INC8", tipo_categoria="cocina")
    db.execute("INSERT INTO receta_insumos VALUES (%s, %s, 150)", (hamburguesa, carne))
    combo = _combo(db, f, grupos=[("Plato", 1, [(hamburguesa, 0)])])
    _vender_combo(db, f, s, combo, 2, 12000, [("Plato", hamburguesa, 1, 0)])
    confirmar(db)
    assert db.execute("SELECT stock FROM insumos WHERE id = %s", (carne,)).fetchone()["stock"] == 700


def test_lo_elegido_va_con_su_linea_y_no_se_edita(db, f):
    s = f.turno()
    coca, gaseosa = f.producto(stock=5), f.producto(stock=5)
    combo = _combo(db, f, grupos=[("Bebida", 1, [(coca, 0)])])
    linea = _vender_combo(db, f, s, combo, 1, 12000, [("Bebida", coca, 1, 0)])
    confirmar(db)
    with falla(db, "se guarda junto con su línea"):
        db.execute("INSERT INTO detalle_venta_elecciones VALUES (%s, 'Otra', %s, 1, 0)", (linea, coca))
    with falla(db, "no se edita ni se borra"):
        db.execute("UPDATE detalle_venta_elecciones SET cantidad = 3 WHERE detalle_id = %s", (linea,))
    # Un producto que no es combo no lleva elecciones.
    with falla(db, "Solo un combo lleva opciones"):
        _vender_combo(db, f, s, gaseosa, 1, 10000, [("Bebida", coca, 1, 0)])


def test_costo_desde_hasta_alcanza_y_bloqueo(db, f):
    papas = f.producto(costo=1000, stock=10)
    coca, cerveza = f.producto(costo=1500, stock=3), f.producto(costo=2500, stock=1)
    combo = _combo(db, f, fijos=[(papas, 2)], grupos=[("Bebida", 1, [(coca, 0), (cerveza, 2000)])])
    a = _articulo(db, combo)
    assert (a["costo"], a["costo_max"], a["tiene_grupos"], a["bloqueo"]) == (3500, 4500, True, None)
    # Con Coca-Cola deja 8500 de 12000 (71%); con cerveza 9500 de 14000 (68%):
    # más plata, menos porcentaje.
    assert (a["margen_min"], a["margen_max"]) == (68, 71)
    # Papas para 5 combos; bebidas 3 + 1 = 4.
    assert a["alcanza"] == 4

    db.execute("UPDATE articulos SET activo = false WHERE id = %s", (cerveza,))
    a = _articulo(db, combo)
    assert (a["costo_max"], a["alcanza"], a["bloqueo"]) == (3500, 3, None)
    db.execute("UPDATE articulos SET activo = false WHERE id IN (%s, %s)", (coca, papas))
    a = _articulo(db, combo)
    assert a["alcanza"] == 0
    assert a["bloqueo"].endswith("está desactivado; el grupo Bebida no tiene opciones activas")


def test_combo_sin_grupos_sigue_igual(db, f):
    gaseosa = f.producto(costo=2000, stock=7)
    combo = _combo(db, f, fijos=[(gaseosa, 2)])
    a = _articulo(db, combo)
    assert (a["costo"], a["costo_max"], a["tiene_grupos"], a["alcanza"], a["bloqueo"]) == (4000, 4000, False, 3, None)
    assert (a["margen_min"], a["margen_max"]) == (67, 67)


def test_elecciones_de_cuenta_solo_con_la_cuenta_abierta(db, f):
    coca = f.producto(stock=5)
    combo = _combo(db, f, grupos=[("Bebida", 1, [(coca, 0)])])
    cuenta = db.execute("INSERT INTO cuentas (alias, abierta_por) VALUES ('Mesa', %s) RETURNING id",
                        (f.usuario(),)).fetchone()["id"]
    item = db.execute("INSERT INTO cuenta_items (cuenta_id, articulo_id, cantidad, precio_unit) VALUES (%s, %s, 1, 12000) RETURNING id",
                      (cuenta, combo)).fetchone()["id"]
    db.execute("INSERT INTO cuenta_item_elecciones VALUES (%s, 'Bebida', %s, 1, 0)", (item, coca))
    confirmar(db)
    assert db.execute("SELECT texto_elecciones(NULL, %s) AS t", (item,)).fetchone()["t"] == db.execute(
        "SELECT nombre FROM articulos WHERE id = %s", (coca,)).fetchone()["nombre"]
    db.execute("UPDATE cuentas SET cancelada_en = now() WHERE id = %s", (cuenta,))
    with falla(db, "ya está cerrada"):
        db.execute("INSERT INTO cuenta_item_elecciones VALUES (%s, 'Otra', %s, 1, 0)", (item, coca))
