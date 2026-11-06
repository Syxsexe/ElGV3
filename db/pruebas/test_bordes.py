"""Casos límite: concurrencia en el cierre de caja, migraciones parciales y
reglas que se revisan también al borrar o editar (no solo al insertar)."""
import os
import uuid

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

import migrar
from ayudas import Fabrica, confirmar, falla


def test_cierre_de_turno_espera_a_una_venta_en_curso(url_prueba):
    # Datos confirmados de verdad: dos conexiones no ven lo que la otra no ha confirmado.
    with psycopg.connect(url_prueba, autocommit=True, row_factory=dict_row) as base:
        with base.transaction():
            fb = Fabrica(base)
            turno, prod = fb.turno(), fb.producto(precio=1000)

    cajero_a = psycopg.connect(url_prueba, row_factory=dict_row)
    cajero_b = psycopg.connect(url_prueba, row_factory=dict_row)
    try:
        # A está registrando una venta (sin confirmar) mientras B intenta cerrar.
        Fabrica(cajero_a).venta(turno, [(prod, 1, 1000)], pagos=[("efectivo", 1000)])
        cajero_b.execute("SET lock_timeout = '300ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            Fabrica(cajero_b).cerrar_turno(turno, {}, digital=0)
        cajero_b.rollback()

        cajero_a.commit()  # la venta entra al turno abierto
        Fabrica(cajero_b).cerrar_turno(turno, {1000: 1}, digital=0)
        cajero_b.commit()

        with pytest.raises(psycopg.Error, match="ya está cerrado"):
            Fabrica(cajero_a).venta(turno, [(prod, 1, 1000)], pagos=[("efectivo", 1000)])
    finally:
        cajero_a.close()
        cajero_b.close()


def test_migracion_que_falla_no_deshace_las_anteriores(tmp_path, monkeypatch):
    (tmp_path / "0001_bien.sql").write_text("CREATE TABLE tabla_bien (id int);")
    (tmp_path / "0002_mal.sql").write_text("CREATE TABLE tabla_mal (id int); SELECT 1 / 0;")
    monkeypatch.setattr(migrar, "CARPETA", tmp_path)

    admin = os.environ["PRUEBAS_DATABASE_URL"]
    nombre = f"elg_prueba_mig_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{nombre}"')
    url = make_conninfo(**{**conninfo_to_dict(admin), "dbname": nombre})
    try:
        with pytest.raises(psycopg.errors.DivisionByZero):
            migrar.aplicar(url, verbose=False)
        with psycopg.connect(url) as conn:
            versiones = [r[0] for r in conn.execute("SELECT version FROM schema_migraciones")]
            tablas = {r[0] for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'tabla_%'")}
        assert versiones == ["0001_bien"]
        assert tablas == {"tabla_bien"}
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)')


def test_solo_una_caja_se_cuenta_en_denominaciones(db):
    with falla(db, "cajas_una_con_denominaciones"):
        db.execute("INSERT INTO cajas (nombre, usa_denominaciones) VALUES ('Caja menor', true)")


def test_plata_solo_a_cajas_registradas_en_el_turno(db, f):
    uid = f.usuario()
    s = db.execute("INSERT INTO sesiones_caja (abierta_por) VALUES (%s) RETURNING id", (uid,)).fetchone()["id"]
    db.execute("INSERT INTO sesion_cajas (sesion_id, caja_id, base) VALUES (%s, %s, 0)", (s, f.caja("Efectivo")))
    prod = f.producto(precio=1000)
    with falla(db, "Digital no está registrada en el turno"):
        f.venta(s, [(prod, 1, 1000)], pagos=[("nequi", 1000)])
    with falla(db, "Digital no está registrada en el turno"):
        f.gasto(s, [("transferencia", 1000)])
    f.venta(s, [(prod, 1, 1000)], pagos=[("efectivo", 1000)])
    confirmar(db)


def test_factura_rechazada_no_impide_reemitir(db, f):
    s, prod = f.turno(), f.producto(precio=1000)
    v = f.venta(s, [(prod, 1, 1000)], pagos=[("efectivo", 1000)])
    sql = ("INSERT INTO documentos_fiscales (tipo, resolucion_id, prefijo, consecutivo, venta_id, "
           "adquiriente_id, adq_nombre, estado) "
           "SELECT 'FEV', r.id, 'FE', %s, %s, t.id, t.nombre, %s "
           "FROM resoluciones r, terceros t WHERE r.prefijo = 'FE' AND t.nombre = 'CONSUMIDOR FINAL'")
    db.execute("INSERT INTO resoluciones (tipo_documento, prefijo, rango_inicio, rango_fin, consecutivo_actual, "
               "fecha_autorizacion, fecha_vencimiento) VALUES ('FEV', 'FE', 1, 100, 0, '2026-01-01', '2028-01-01')")
    db.execute(sql, (1, v, "rechazado"))
    db.execute(sql, (2, v, "aceptado"))  # la rechazada nunca fue válida
    with falla(db, "documento fiscal vigente"):
        db.execute(sql, (3, v, "pendiente"))


def test_ciclo_entre_preparaciones_sin_platos_tambien_se_rechaza(db, f):
    a, b = f.insumo(costo=1), f.insumo(costo=1)
    db.execute("INSERT INTO preparaciones VALUES (%s, 1), (%s, 1)", (a, b))
    db.execute("INSERT INTO receta_preparacion VALUES (%s, %s, 1)", (a, b))
    with falla(db, "forman un ciclo"):
        db.execute("INSERT INTO receta_preparacion VALUES (%s, %s, 1)", (b, a))


def test_no_se_rebaja_una_compra_ya_pagada(db, f):
    s, prov = f.turno(base_efectivo=500000), f.proveedor()
    prod = f.producto()
    compra = f.compra(prov, [(prod, None, 10, 10000)])
    f.pago_compra(s, compra, [("efectivo", 100000)])
    confirmar(db)
    with falla(db, "se le pagaría"):
        db.execute("UPDATE compra_lineas SET costo_unit = 6000 WHERE compra_id = %s", (compra,))
    with falla(db, "se le pagaría"):
        db.execute("DELETE FROM compra_lineas WHERE compra_id = %s", (compra,))
    db.execute("UPDATE compra_lineas SET costo_unit = 12000 WHERE compra_id = %s", (compra,))  # subirla sí
    confirmar(db)


def test_borrar_el_subtipo_deja_el_articulo_invalido(db, f):
    prod = f.producto()
    confirmar(db)
    with falla(db, "no tiene su fila de subtipo"):
        db.execute("DELETE FROM productos WHERE articulo_id = %s", (prod,))
    with falla(db, "no tiene su fila de subtipo"):
        db.execute("DELETE FROM productos WHERE articulo_id = %s", (prod,))
        db.execute("UPDATE articulos SET tipo = 'servicio' WHERE id = %s", (prod,))
    # Cambiar de tipo con su subtipo nuevo en la misma transacción sí es válido.
    db.execute("DELETE FROM productos WHERE articulo_id = %s", (prod,))
    db.execute("UPDATE articulos SET tipo = 'servicio' WHERE id = %s", (prod,))
    db.execute("INSERT INTO servicios (articulo_id) VALUES (%s)", (prod,))
    confirmar(db)


def test_cambio_de_caja_de_un_metodo_espera_al_pago_en_curso(url_prueba):
    # Sin el FOR SHARE de 0016, el cambio de caja no veía el pago sin confirmar
    # (el bloqueo de la FK no choca con el UPDATE) y los dos confirmaban.
    with psycopg.connect(url_prueba, autocommit=True, row_factory=dict_row) as base:
        with base.transaction():
            fb = Fabrica(base)
            turno, prod = fb.turno(), fb.producto(precio=1000)
            metodo = base.execute(
                "INSERT INTO metodos_pago (codigo, nombre, caja_id) "
                "SELECT %s, 'QR prueba', id FROM cajas WHERE nombre = 'Digital' RETURNING id",
                (f"qr_{uuid.uuid4().hex[:6]}",)).fetchone()["id"]

    cajero = psycopg.connect(url_prueba, row_factory=dict_row)
    admin = psycopg.connect(url_prueba, row_factory=dict_row)
    try:
        venta = Fabrica(cajero).venta(turno, [(prod, 1, 1000)])
        cajero.execute("INSERT INTO pagos_venta (venta_id, metodo_pago_id, monto) VALUES (%s, %s, 1000)", (venta, metodo))
        admin.execute("SET lock_timeout = '300ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            admin.execute("UPDATE metodos_pago SET caja_id = (SELECT id FROM cajas WHERE nombre = 'Efectivo') WHERE id = %s",
                          (metodo,))
        admin.rollback()
        cajero.commit()
        with pytest.raises(psycopg.Error, match="no puede cambiar de caja"):
            admin.execute("UPDATE metodos_pago SET caja_id = (SELECT id FROM cajas WHERE nombre = 'Efectivo') WHERE id = %s",
                          (metodo,))
        admin.rollback()
        Fabrica(admin).cerrar_turno(turno, {}, digital=1000)  # deja la base sin turno abierto
        admin.commit()
    finally:
        cajero.close()
        admin.close()
