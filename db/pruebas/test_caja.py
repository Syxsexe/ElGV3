"""Grupo 4: turnos, conteo de cierre, movimientos y el esperado por caja."""
from decimal import Decimal

from ayudas import confirmar, falla


def _caja(db, sesion, nombre):
    return db.execute(
        "SELECT esperado, contado, diferencia, diferencia_apertura FROM v_sesion_cajas "
        "WHERE sesion_id = %s AND caja = %s", (sesion, nombre)).fetchone()


def test_solo_un_turno_abierto(db, f):
    f.turno()
    with falla(db, "sesiones_caja_un_turno_abierto"):
        f.turno()


def test_un_turno_no_se_crea_ya_cerrado(db, f):
    uid = f.usuario()
    with falla(db, "se abre abierto"):
        db.execute("INSERT INTO sesiones_caja (abierta_por, cerrada_por, cerrada_en) "
                   "VALUES (%s, %s, now())", (uid, uid))


def test_cerrar_exige_conteo_de_cada_caja(db, f):
    s = f.turno()
    with falla(db, "Falta el conteo"):
        db.execute("UPDATE sesiones_caja SET cerrada_por = abierta_por, cerrada_en = now() WHERE id = %s", (s,))


def test_contado_de_efectivo_igual_a_las_denominaciones(db, f):
    s = f.turno()
    db.execute("UPDATE sesion_cajas SET contado = 99999 WHERE sesion_id = %s", (s,))
    db.execute("INSERT INTO conteo_denominaciones SELECT %s, id, 2 FROM denominaciones WHERE valor = 50000", (s,))
    with falla(db, "no coincide con las denominaciones"):
        db.execute("UPDATE sesiones_caja SET cerrada_por = abierta_por, cerrada_en = now() WHERE id = %s", (s,))


def test_turno_cerrado_no_admite_cambios(db, f):
    s = f.turno(base_efectivo=50000)
    f.cerrar_turno(s, {50000: 1}, digital=0)
    with falla(db, "ya está cerrado"):
        db.execute("UPDATE sesiones_caja SET notas = 'x' WHERE id = %s", (s,))
    with falla(db, "ya está cerrado"):
        f.venta(s, [(f.producto(precio=1000), 1, 1000)], pagos=[("efectivo", 1000)])
    with falla(db, "ya está cerrado"):
        f.gasto(s, [("efectivo", 1000)])
    with falla(db, "ya está cerrado"):
        db.execute("UPDATE sesion_cajas SET contado = 0 WHERE sesion_id = %s", (s,))
    with falla(db, "no se borran"):
        db.execute("DELETE FROM sesiones_caja WHERE id = %s", (s,))


def test_movimientos_de_caja_segun_tipo(db, f):
    s = f.turno()
    ef, dig, uid = f.caja("Efectivo"), f.caja("Digital"), f.usuario()
    sql = ("INSERT INTO movimientos_caja (sesion_id, tipo, caja_origen_id, caja_destino_id, monto, motivo, usuario_id) "
           "VALUES (%s, %s, %s, %s, 1000, 'x', %s)")
    db.execute(sql, (s, "retiro", ef, None, uid))
    db.execute(sql, (s, "ingreso", None, ef, uid))
    db.execute(sql, (s, "traslado", ef, dig, uid))
    for tipo, origen, destino in (("retiro", None, ef), ("ingreso", ef, None), ("traslado", ef, ef)):
        with falla(db, "movimientos_caja_cajas_segun_tipo"):
            db.execute(sql, (s, tipo, origen, destino, uid))
    with falla(db, "solo inserción"):
        db.execute("DELETE FROM movimientos_caja WHERE sesion_id = %s", (s,))


def test_esperado_suma_entradas_y_resta_salidas_por_caja(db, f):
    s = f.turno(base_efectivo=100000, base_digital=20000)
    cliente = f.cliente()
    deuda = f.cargo(cliente, 30000)
    prod = f.producto(precio=10000)
    # Venta de 50.000: 30.000 en efectivo, 20.000 por Nequi.
    f.venta(s, [(prod, 5, 10000)], pagos=[("efectivo", 30000), ("nequi", 20000)])
    # Abono de fiado de 30.000 en efectivo.
    f.abono(cliente, [(deuda, 30000)], sesion_id=s)
    # Gasto de 8.000 en efectivo y consignación de 50.000 de Efectivo a Digital.
    f.gasto(s, [("efectivo", 8000)])
    db.execute("INSERT INTO movimientos_caja (sesion_id, tipo, caja_origen_id, caja_destino_id, monto, motivo, usuario_id) "
               "VALUES (%s, 'traslado', %s, %s, 50000, 'Consignación', %s)",
               (s, f.caja("Efectivo"), f.caja("Digital"), f.usuario()))
    confirmar(db)
    # Efectivo: 100.000 + 30.000 + 30.000 − 8.000 − 50.000 = 102.000
    # Digital:   20.000 + 20.000 + 50.000 = 90.000
    assert _caja(db, s, "Efectivo")["esperado"] == Decimal("102000")
    assert _caja(db, s, "Digital")["esperado"] == Decimal("90000")

    f.cerrar_turno(s, {100000: 1, 2000: 1}, digital=90000)
    efectivo = _caja(db, s, "Efectivo")
    assert efectivo["contado"] == Decimal("102000") and efectivo["diferencia"] == 0


def test_diferencia_de_apertura_y_anulacion_en_otro_turno(db, f):
    s1 = f.turno(base_efectivo=50000)
    gasto = f.gasto(s1, [("efectivo", 10000)])
    f.cerrar_turno(s1, {20000: 2}, digital=0)  # contó 40.000: cuadra (50.000 − 10.000)
    assert _caja(db, s1, "Efectivo")["diferencia"] == 0

    s2 = f.turno(base_efectivo=35000)  # faltan 5.000 entre turnos
    assert _caja(db, s2, "Efectivo")["diferencia_apertura"] == Decimal("-5000")

    # Se anula el gasto del turno 1 en el turno 2: la plata vuelve en el turno 2.
    db.execute("INSERT INTO anulaciones_egreso (egreso_id, sesion_id, usuario_id, motivo) "
               "VALUES (%s, %s, %s, 'Se registró dos veces')", (gasto, s2, f.usuario()))
    assert _caja(db, s2, "Efectivo")["esperado"] == Decimal("45000")
    assert _caja(db, s1, "Efectivo")["diferencia"] == 0  # el turno cerrado no cambia


def test_no_hay_via_de_escape_para_turnos_cerrados(db, f):
    # La vía elg.migracion existía para cargar datos históricos; ya no hay migración.
    db.execute("SET LOCAL elg.migracion = 'on'")
    uid = f.usuario()
    with falla(db, "se abre abierto"):
        db.execute("INSERT INTO sesiones_caja (abierta_por, cerrada_por, cerrada_en) "
                   "VALUES (%s, %s, now())", (uid, uid))
    s = f.turno()
    f.cerrar_turno(s, {}, digital=0)
    with falla(db, "ya está cerrado"):
        f.venta(s, [(f.producto(precio=1000), 1, 1000)], pagos=[("efectivo", 1000)])


def test_metodo_con_pagos_no_cambia_de_caja(db, f):
    efectivo, digital = f.caja("Efectivo"), f.caja("Digital")
    db.execute("UPDATE metodos_pago SET caja_id = %s WHERE codigo = 'tarjeta'", (efectivo,))  # sin pagos: sí
    db.execute("UPDATE metodos_pago SET caja_id = %s WHERE codigo = 'tarjeta'", (digital,))
    s = f.turno()
    f.venta(s, [(f.producto(precio=1000), 1, 1000)], pagos=[("nequi", 1000)])
    with falla(db, "no puede cambiar de caja"):
        db.execute("UPDATE metodos_pago SET caja_id = %s WHERE codigo = 'nequi'", (efectivo,))
    db.execute("UPDATE metodos_pago SET nombre = 'Nequi QR', activo = false WHERE codigo = 'nequi'")


def test_el_desglose_de_flujos_suma_el_esperado(db, f):
    s = f.turno(base_efectivo=10000, base_digital=5000)
    cliente = f.cliente()
    deuda = f.cargo(cliente, 4000)
    f.venta(s, [(f.producto(precio=6000), 1, 6000)], pagos=[("efectivo", 1000), ("nequi", 5000)])
    f.abono(cliente, [(deuda, 4000)], sesion_id=s)
    gasto = f.gasto(s, [("efectivo", 2000)])
    db.execute("INSERT INTO anulaciones_egreso (egreso_id, sesion_id, usuario_id, motivo) "
               "VALUES (%s, %s, %s, 'Repetido')", (gasto, s, f.usuario()))
    confirmar(db)
    flujos = {(r["caja"], r["concepto"]): r["monto"] for r in db.execute(
        "SELECT c.nombre AS caja, fc.concepto, sum(fc.monto) AS monto FROM v_flujos_caja fc "
        "JOIN cajas c ON c.id = fc.caja_id WHERE fc.sesion_id = %s GROUP BY 1, 2", (s,))}
    assert flujos == {("Efectivo", "venta"): 1000, ("Digital", "venta"): 5000, ("Efectivo", "abono"): 4000,
                      ("Efectivo", "egreso"): -2000, ("Efectivo", "anulacion_egreso"): 2000}
    for caja, base in (("Efectivo", 10000), ("Digital", 5000)):
        neto = sum(m for (c, _), m in flujos.items() if c == caja)
        assert _caja(db, s, caja)["esperado"] == base + neto
