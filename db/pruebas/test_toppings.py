"""Toppings de los platos (0025): qué acepta cada plato, la foto en la línea,
el texto junto al nombre y el stock de sus insumos."""
import uuid

from ayudas import falla


def _adicional(db, f, insumo, porcion, precio=2000):
    aid = db.execute(
        "INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta) "
        "VALUES ('adicional', %s, %s, %s, %s) RETURNING id",
        (f"Top {uuid.uuid4().hex[:5]}", f.categoria("cocina"), f.impuesto("INC8"), precio)).fetchone()["id"]
    db.execute("INSERT INTO adicionales VALUES (%s, 'adicional', %s, %s)", (aid, insumo, porcion))
    return aid


def _stock(db, insumo):
    return db.execute("SELECT stock FROM insumos WHERE id = %s", (insumo,)).fetchone()["stock"]


def _plato_con_toppings(db, f):
    huevo, queso = f.insumo(costo=500, unidad="und"), f.insumo(costo=20)
    plato = f.producto(precio=15000, impuesto="INC8", tipo_categoria="cocina", stock=0)
    t_huevo, t_queso = _adicional(db, f, huevo, 1, 2000), _adicional(db, f, queso, 30, 3000)
    db.execute("INSERT INTO plato_toppings (plato_id, adicional_id) VALUES (%s, %s), (%s, %s)", (plato, t_huevo, plato, t_queso))
    return plato, (huevo, queso), (t_huevo, t_queso)


def test_vender_un_plato_con_toppings_descuenta_sus_insumos(db, f):
    plato, (huevo, queso), (t_huevo, t_queso) = _plato_con_toppings(db, f)
    venta = db.execute("INSERT INTO ventas (sesion_id, usuario_id) VALUES (%s, %s) RETURNING id",
                       (f.turno(), f.usuario())).fetchone()["id"]
    linea = uuid.uuid4()
    # Los toppings van antes que su línea (FK diferida); 2 platos con huevo y queso.
    db.execute("INSERT INTO detalle_venta_toppings VALUES (%s, %s, 2000), (%s, %s, 3000)", (linea, t_huevo, linea, t_queso))
    db.execute("INSERT INTO detalle_venta (id, venta_id, articulo_id, cantidad, precio_unit, impuesto_id) "
               "VALUES (%s, %s, %s, 2, 20000, %s)", (linea, venta, plato, f.impuesto("INC8")))
    db.execute("SET CONSTRAINTS detalle_venta_toppings_de_plato IMMEDIATE")  # es un plato: pasa
    assert (_stock(db, huevo), _stock(db, queso)) == (-2, -60)  # se vende y avisa, como los platos
    texto = db.execute("SELECT texto_elecciones(%s, NULL) AS t", (linea,)).fetchone()["t"]
    nombres = db.execute("SELECT string_agg(nombre, ', ' ORDER BY nombre) AS n FROM articulos WHERE id IN (%s, %s)",
                         (t_huevo, t_queso)).fetchone()["n"]
    assert texto == f"con {nombres}"
    with falla(db, "no se edita ni se borra"):
        db.execute("DELETE FROM detalle_venta_toppings WHERE detalle_id = %s", (linea,))


def test_los_toppings_van_con_su_linea_y_solo_en_platos(db, f):
    plato, _, (t_huevo, _) = _plato_con_toppings(db, f)
    s = f.turno()
    venta = f.venta(s, [(plato, 1, 15000)], pagos=[("efectivo", 15000)])
    linea = db.execute("SELECT id FROM detalle_venta WHERE venta_id = %s", (venta,)).fetchone()["id"]
    with falla(db, "junto con su línea de venta"):
        db.execute("INSERT INTO detalle_venta_toppings VALUES (%s, %s, 2000)", (linea, t_huevo))


def test_solo_un_plato_lleva_toppings(db, f):
    _, _, (t_huevo, _) = _plato_con_toppings(db, f)
    gaseosa = f.producto(precio=3000)
    with falla(db, "Solo los platos de cocina llevan toppings"):
        db.execute("INSERT INTO plato_toppings (plato_id, adicional_id) VALUES (%s, %s)", (gaseosa, t_huevo))
    # En una venta basta con que la línea sea un producto (un plato que pasó a
    # tienda con una cuenta abierta se puede cobrar); un servicio, no.
    venta = db.execute("INSERT INTO ventas (sesion_id, usuario_id) VALUES (%s, %s) RETURNING id",
                       (f.turno(), f.usuario())).fetchone()["id"]
    linea = uuid.uuid4()
    db.execute("INSERT INTO detalle_venta_toppings VALUES (%s, %s, 2000)", (linea, t_huevo))
    db.execute("INSERT INTO detalle_venta (id, venta_id, articulo_id, cantidad, precio_unit, impuesto_id) "
               "SELECT %s, %s, id, 1, 15000, impuesto_id FROM articulos WHERE id = %s", (linea, venta, f.inscripcion()))
    with falla(db, "Solo un plato lleva toppings"):
        db.execute("SET CONSTRAINTS detalle_venta_toppings_de_plato IMMEDIATE")


def test_un_plato_con_toppings_sigue_en_cocina_y_se_marca(db, f):
    plato, _, (t_huevo, _) = _plato_con_toppings(db, f)
    fila = db.execute("SELECT tiene_toppings FROM v_articulos WHERE id = %s", (plato,)).fetchone()
    assert fila["tiene_toppings"] is True
    assert db.execute("SELECT es_topping FROM v_articulos WHERE id = %s", (t_huevo,)).fetchone()["es_topping"] is True
    # Si el plato se desactiva, el topping vuelve a venderse suelto.
    db.execute("UPDATE articulos SET activo = false WHERE id = %s", (plato,))
    assert db.execute("SELECT es_topping FROM v_articulos WHERE id = %s", (t_huevo,)).fetchone()["es_topping"] is False
    db.execute("UPDATE articulos SET activo = true WHERE id = %s", (plato,))
    with falla(db, "acepta toppings: debe seguir en una categoría de cocina"):
        db.execute("UPDATE articulos SET categoria_id = %s WHERE id = %s", (f.categoria("tienda"), plato))
