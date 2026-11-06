"""0017: búsqueda sin tildes, costo de cada tipo de artículo y vistas del catálogo."""
from decimal import Decimal


def test_normalizar_quita_tildes_y_mayusculas(db):
    fila = db.execute("SELECT normalizar('Crêpe de PIÑA Ácida') AS a, normalizar('Häagen-Dazs Açaí') AS b").fetchone()
    assert fila == {"a": "crepe de pina acida", "b": "haagen-dazs acai"}


def test_costo_de_cada_tipo_de_articulo(db, f):
    gaseosa = f.producto(precio=3000, costo=1800)
    papas = f.producto(precio=4000, costo=2500)
    combo = db.execute(
        "INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta) "
        "VALUES ('combo', 'Combo', %s, %s, 6000) RETURNING id", (f.categoria("cocina"), f.impuesto("INC8"))).fetchone()["id"]
    db.execute("INSERT INTO combos (articulo_id) VALUES (%s)", (combo,))
    db.execute("INSERT INTO combo_productos VALUES (%s, %s, 2), (%s, %s, 1)", (combo, gaseosa, combo, papas))
    queso = f.insumo(costo=Decimal("12.5"))
    extra = db.execute(
        "INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta) "
        "VALUES ('adicional', 'Queso extra', %s, %s, 2000) RETURNING id", (f.categoria("cocina"), f.impuesto("INC8"))).fetchone()["id"]
    db.execute("INSERT INTO adicionales (articulo_id, insumo_id, cantidad) VALUES (%s, %s, 40)", (extra, queso))

    costos = {r["id"]: r["costo"] for r in db.execute(
        "SELECT id, costo FROM v_articulos WHERE id = ANY (%s)", ([gaseosa, combo, extra, f.inscripcion()],))}
    assert costos == {gaseosa: Decimal("1800"), combo: Decimal("6100"), extra: Decimal("500"), f.inscripcion(): 0}


def test_v_insumos_da_el_costo_calculado_de_las_preparaciones(db, f):
    harina, leche = f.insumo(costo=4), f.insumo(costo=2, unidad="ml")
    masa = f.insumo(costo=999)  # el costo_unitario de una preparación se ignora
    db.execute("INSERT INTO preparaciones VALUES (%s, 500)", (masa,))
    db.execute("INSERT INTO receta_preparacion VALUES (%s, %s, 200), (%s, %s, 300)", (masa, harina, masa, leche))
    fila = db.execute("SELECT es_preparacion, rendimiento, costo FROM v_insumos WHERE id = %s", (masa,)).fetchone()
    assert fila == {"es_preparacion": True, "rendimiento": Decimal("500.000"), "costo": Decimal("2.8")}
