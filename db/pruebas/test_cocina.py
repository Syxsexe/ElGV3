"""Inventario de cocina (0022): recetas con insumos y productos, stock de
insumos, producción de preparaciones y cuántos platos alcanzan."""
from decimal import Decimal

from ayudas import falla


def _insumo(db, i):
    return db.execute("SELECT stock FROM insumos WHERE id = %s", (i,)).fetchone()["stock"]


def _producto(db, p):
    return db.execute("SELECT stock, precio_costo FROM productos WHERE articulo_id = %s", (p,)).fetchone()


def _plato(db, f, insumos=(), productos=(), precio=15000):
    """insumos / productos = [(id, cantidad)]."""
    plato = f.producto(precio=precio, impuesto="INC8", tipo_categoria="cocina", stock=0)
    for i, c in insumos:
        db.execute("INSERT INTO receta_insumos VALUES (%s, %s, %s)", (plato, i, c))
    for p, c in productos:
        db.execute("INSERT INTO receta_productos VALUES (%s, %s, %s)", (plato, p, c))
    return plato


def test_costo_del_plato_con_insumos_y_productos(db, f):
    carne, pan = f.insumo(costo=20), f.producto(costo=800, stock=10)
    plato = _plato(db, f, insumos=[(carne, 150)], productos=[(pan, 1)])
    assert _producto(db, plato)["precio_costo"] == Decimal("3800.00")  # 150 g × 20 + 1 × 800
    # Cambia el costo del pan (una compra): el plato se recalcula.
    db.execute("UPDATE productos SET precio_costo = 1000 WHERE articulo_id = %s", (pan,))
    assert _producto(db, plato)["precio_costo"] == Decimal("4000.00")
    db.execute("UPDATE insumos SET costo_unitario = 30 WHERE id = %s", (carne,))
    assert _producto(db, plato)["precio_costo"] == Decimal("5500.00")


def test_en_la_receta_solo_productos_de_tienda(db, f):
    otro_plato = f.producto(tipo_categoria="cocina", impuesto="INC8", stock=0)
    plato = _plato(db, f)
    with falla(db, "solo van productos de la tienda"):
        db.execute("INSERT INTO receta_productos VALUES (%s, %s, 1)", (plato, otro_plato))


def test_vender_un_plato_descuenta_su_receta_sin_frenar(db, f):
    s = f.turno()
    queso, pan = f.insumo(costo=2), f.producto(costo=800, stock=1)
    db.execute("UPDATE insumos SET stock = 100 WHERE id = %s", (queso,))
    plato = _plato(db, f, insumos=[(queso, 80)], productos=[(pan, 1)])
    f.venta(s, [(plato, 2, 15000)], pagos=[("efectivo", 30000)])
    # Se vende aunque no alcance: el insumo y el pan quedan en negativo para ajustarlos.
    assert _insumo(db, queso) == Decimal("-60")
    assert _producto(db, pan)["stock"] == -1


def test_adicionales_y_combos_con_platos_descuentan_insumos(db, f):
    s = f.turno()
    queso, salchicha, gaseosa = f.insumo(), f.insumo(), f.producto(stock=5)
    perro = _plato(db, f, insumos=[(salchicha, 1)])
    extra = db.execute(
        "INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta) "
        "VALUES ('adicional', 'Queso extra', %s, %s, 2000) RETURNING id",
        (f.categoria("cocina"), f.impuesto("INC8"))).fetchone()["id"]
    db.execute("INSERT INTO adicionales VALUES (%s, 'adicional', %s, 30)", (extra, queso))
    combo = db.execute(
        "INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta) "
        "VALUES ('combo', 'Combo perro', %s, %s, 15000) RETURNING id",
        (f.categoria("cocina"), f.impuesto("INC8"))).fetchone()["id"]
    db.execute("INSERT INTO combos (articulo_id) VALUES (%s)", (combo,))
    db.execute("INSERT INTO combo_productos VALUES (%s, %s, 1), (%s, %s, 1)", (combo, perro, combo, gaseosa))
    f.venta(s, [(combo, 2, 15000), (extra, 1, 2000)], pagos=[("efectivo", 32000)])
    assert (_insumo(db, salchicha), _insumo(db, queso), _producto(db, gaseosa)["stock"]) == (-2, -30, 3)


def test_compras_de_insumos_suman_y_revierten(db, f):
    prov, queso = f.proveedor(), f.insumo()
    compra = f.compra(prov, [(None, queso, 1000, 2)])
    assert _insumo(db, queso) == 1000
    db.execute("UPDATE compra_lineas SET cantidad = 800 WHERE compra_id = %s", (compra,))
    assert _insumo(db, queso) == 800
    db.execute("DELETE FROM compra_lineas WHERE compra_id = %s", (compra,))
    assert _insumo(db, queso) == 0


def test_producir_una_preparacion(db, f):
    tomate, ajo = f.insumo(costo=4), f.insumo(costo=10)
    db.execute("UPDATE insumos SET stock = 5000 WHERE id = %s", (tomate,))
    salsa = f.insumo()
    db.execute("INSERT INTO preparaciones VALUES (%s, 2000)", (salsa,))  # un lote rinde 2000 g
    db.execute("INSERT INTO receta_preparacion VALUES (%s, %s, 2500), (%s, %s, 50)", (salsa, tomate, salsa, ajo))
    db.execute("INSERT INTO producciones (preparacion_id, lotes, cantidad, usuario_id) VALUES (%s, 1.5, 3000, %s)",
               (salsa, f.usuario()))
    assert (_insumo(db, tomate), _insumo(db, ajo), _insumo(db, salsa)) == (1250, -75, 3000)
    with falla(db, "no se edita ni se borra"):
        db.execute("DELETE FROM producciones WHERE preparacion_id = %s", (salsa,))
    # Un plato con la salsa descuenta la salsa, no sus ingredientes.
    s = f.turno()
    pasta = _plato(db, f, insumos=[(salsa, 200)])
    f.venta(s, [(pasta, 1, 15000)], pagos=[("efectivo", 15000)])
    assert (_insumo(db, salsa), _insumo(db, tomate)) == (2800, 1250)


def test_cuantos_platos_alcanzan(db, f):
    carne, pan = f.insumo(), f.producto(stock=3)
    db.execute("UPDATE insumos SET stock = 1000 WHERE id = %s", (carne,))
    plato = _plato(db, f, insumos=[(carne, 150)], productos=[(pan, 1)])
    alcanza = lambda: db.execute("SELECT alcanza FROM v_articulos WHERE id = %s", (plato,)).fetchone()["alcanza"]
    assert alcanza() == 3  # el pan limita (la carne daría para 6)
    db.execute("UPDATE productos SET stock = 10 WHERE articulo_id = %s", (pan,))
    assert alcanza() == 6
    db.execute("UPDATE insumos SET stock = -20 WHERE id = %s", (carne,))
    assert alcanza() == 0
    sin_receta = _plato(db, f)
    assert db.execute("SELECT alcanza, tiene_receta FROM v_articulos WHERE id = %s", (sin_receta,)).fetchone() == \
        {"alcanza": None, "tiene_receta": False}


def test_lo_que_va_en_un_plato_no_frena_lo_directo(db, f):
    s, pan = f.turno(), f.producto(stock=1)
    plato = _plato(db, f, productos=[(pan, 1)])
    f.venta(s, [(pan, 1, 1500), (plato, 1, 15000)], pagos=[("efectivo", 16500)])
    assert _producto(db, pan)["stock"] == -1
    with falla(db, r"hay 0, se necesitan 1"):
        f.venta(s, [(pan, 1, 1500)], pagos=[("efectivo", 1500)])


def test_sin_cadenas_ni_recategorizar(db, f):
    a, b = f.producto(stock=1), f.producto(stock=1)
    with falla(db, "Solo los platos de cocina llevan productos"):
        db.execute("INSERT INTO receta_productos VALUES (%s, %s, 2)", (a, b))
    pan = f.producto(stock=1)
    plato = _plato(db, f, productos=[(pan, 1)])
    with falla(db, "debe seguir en una categoría de tienda"):
        db.execute("UPDATE articulos SET categoria_id = %s WHERE id = %s", (f.categoria("cocina"), pan))
    with falla(db, "debe seguir en una categoría de cocina"):
        db.execute("UPDATE articulos SET categoria_id = %s WHERE id = %s", (f.categoria("tienda"), plato))


def test_borrar_una_compra_no_abre_recetas(db, f):
    prov, papa = f.proveedor(), f.insumo()
    papas = f.producto(tipo_categoria="cocina", impuesto="INC8", stock=0)
    compra = f.compra(prov, [(papas, None, 10, 1000)])
    db.execute("INSERT INTO receta_insumos VALUES (%s, %s, 200)", (papas, papa))
    db.execute("DELETE FROM compra_lineas WHERE compra_id = %s", (compra,))
    assert _insumo(db, papa) == 0


def test_quitar_la_receta_de_una_preparacion_producida(db, f):
    tomate, salsa = f.insumo(), f.insumo()
    db.execute("INSERT INTO preparaciones VALUES (%s, 1000)", (salsa,))
    db.execute("INSERT INTO receta_preparacion VALUES (%s, %s, 1200)", (salsa, tomate))
    db.execute("INSERT INTO producciones (preparacion_id, lotes, cantidad, usuario_id) VALUES (%s, 1, 1000, %s)",
               (salsa, f.usuario()))
    db.execute("DELETE FROM receta_preparacion WHERE preparacion_id = %s", (salsa,))
    db.execute("DELETE FROM preparaciones WHERE insumo_id = %s", (salsa,))
    assert _insumo(db, salsa) == 1000
