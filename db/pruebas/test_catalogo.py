"""Grupo 2: supertipo artículo, impuestos y caché del costo de los platos."""
from decimal import Decimal

from ayudas import confirmar, falla


def _articulo(db, f, tipo, impuesto="IVA19"):
    return db.execute(
        "INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta) "
        "VALUES (%s, %s, %s, %s, 1000) RETURNING id",
        (tipo, f"Art {tipo}", f.categoria(), f.impuesto(impuesto))).fetchone()["id"]


def test_subtipo_debe_coincidir_con_el_tipo(db, f):
    aid = _articulo(db, f, "producto")
    with falla(db, "foreign key"):
        db.execute("INSERT INTO combos (articulo_id) VALUES (%s)", (aid,))
    db.execute("INSERT INTO productos (articulo_id) VALUES (%s)", (aid,))
    confirmar(db)


def test_articulo_sin_subtipo_no_se_confirma(db, f):
    with falla(db, "no tiene su fila de subtipo"):
        _articulo(db, f, "servicio")


def test_combo_debe_llevar_inc(db, f):
    with falla(db, "debe llevar un impuesto INC"):
        _articulo(db, f, "combo", impuesto="IVA19")
    aid = _articulo(db, f, "combo", impuesto="INC8")
    db.execute("INSERT INTO combos (articulo_id) VALUES (%s)", (aid,))
    confirmar(db)


def test_impuestos_no_se_editan(db, f):
    with falla(db, "no se edita"):
        db.execute("UPDATE impuestos SET tarifa = 16 WHERE codigo = 'IVA19'")
    db.execute("UPDATE impuestos SET nombre = 'IVA general 19%' WHERE codigo = 'IVA19'")


def test_preparacion_no_se_contiene_a_si_misma(db, f):
    adobo = f.insumo()
    db.execute("INSERT INTO preparaciones (insumo_id, rendimiento) VALUES (%s, 1000)", (adobo,))
    with falla(db, "receta_preparacion_no_se_contiene"):
        db.execute("INSERT INTO receta_preparacion VALUES (%s, %s, 10)", (adobo, adobo))


def _costo(db, producto):
    return db.execute("SELECT precio_costo FROM productos WHERE articulo_id = %s",
                      (producto,)).fetchone()["precio_costo"]


def test_costo_del_plato_se_recalcula_con_preparaciones_anidadas(db, f):
    # Adobo: 1000 g de lote con 100 g de sal ($5/g) → $0,5/g.
    # Filete: lote de 500 g con 40 g de adobo + 600 g de pollo ($20/g) → (20 + 12000) / 500 = $24,04/g.
    # Plato: 150 g de filete + 1 pan ($800) → 3606 + 800 = $4406.
    sal, pollo, pan = f.insumo(costo=5), f.insumo(costo=20), f.insumo(costo=800, unidad="und")
    adobo, filete = f.insumo(), f.insumo()
    db.execute("INSERT INTO preparaciones VALUES (%s, 1000), (%s, 500)", (adobo, filete))
    db.execute("INSERT INTO receta_preparacion VALUES (%s, %s, 100), (%s, %s, 40), (%s, %s, 600)",
               (adobo, sal, filete, adobo, filete, pollo))
    plato = f.producto(tipo_categoria="cocina", impuesto="INC8")
    db.execute("INSERT INTO receta_insumos VALUES (%s, %s, 150), (%s, %s, 1)", (plato, filete, plato, pan))
    assert _costo(db, plato) == Decimal("4406.00")

    # Sube la sal a $10/g: adobo $1/g, filete $24,08/g, plato 3612 + 800 = $4412.
    db.execute("UPDATE insumos SET costo_unitario = 10 WHERE id = %s", (sal,))
    assert _costo(db, plato) == Decimal("4412.00")


def test_ciclo_entre_preparaciones_se_rechaza(db, f):
    a, b = f.insumo(costo=1), f.insumo(costo=1)
    db.execute("INSERT INTO preparaciones VALUES (%s, 1), (%s, 1)", (a, b))
    plato = f.producto(tipo_categoria="cocina", impuesto="INC8")
    db.execute("INSERT INTO receta_preparacion VALUES (%s, %s, 1)", (a, b))
    db.execute("INSERT INTO receta_insumos VALUES (%s, %s, 1)", (plato, a))
    with falla(db, "forman un ciclo"):
        db.execute("INSERT INTO receta_preparacion VALUES (%s, %s, 1)", (b, a))
