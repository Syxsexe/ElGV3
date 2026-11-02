"""Grupos 7 y 8: fiado (abonos, condonaciones, cruces) y compras/gastos."""
from decimal import Decimal

from ayudas import confirmar, falla


def _cargo(db, cargo):
    return db.execute("SELECT abonado, condonado, pendiente, vencido FROM v_cargos_credito WHERE id = %s",
                      (cargo,)).fetchone()


def test_cargo_sin_venta_exige_notas(db, f):
    cliente = f.cliente()
    with falla(db, "cargos_credito_con_origen"):
        db.execute("INSERT INTO cargos_credito (cliente_id, monto, vence_en) VALUES (%s, 1000, '2099-01-01')",
                   (cliente,))


def test_un_pago_cubre_varios_cargos_en_una_sola_fila(db, f):
    s, cliente = f.turno(), f.cliente(limite=500000)
    c1, c2 = f.cargo(cliente, 40000), f.cargo(cliente, 70000)
    abono = f.abono(cliente, [(c1, 40000), (c2, 60000)], sesion_id=s)
    confirmar(db)
    assert db.execute("SELECT count(*) AS n FROM abonos_credito WHERE id = %s", (abono,)).fetchone()["n"] == 1
    assert _cargo(db, c1)["pendiente"] == 0
    assert _cargo(db, c2)["pendiente"] == Decimal("10000")
    saldo = db.execute("SELECT saldo, disponible FROM v_saldos_clientes WHERE cliente_id = %s",
                       (cliente,)).fetchone()
    assert saldo == {"saldo": Decimal("10000"), "disponible": Decimal("490000")}


def test_abono_se_aplica_completo_y_al_mismo_cliente(db, f):
    s, cliente, otro = f.turno(), f.cliente(), f.cliente()
    cargo = f.cargo(cliente, 50000)
    with falla(db, "está aplicado por"):  # abono general: ya no existe
        f.abono(cliente, [(cargo, 20000)], sesion_id=s, monto=30000)
    with falla(db, "mismo cliente"):
        f.abono(otro, [(cargo, 10000)], sesion_id=s)


def test_no_se_paga_ni_condona_de_mas(db, f):
    s, cliente = f.turno(), f.cliente()
    cargo = f.cargo(cliente, 50000)
    f.abono(cliente, [(cargo, 30000)], sesion_id=s)
    with falla(db, "pagado de más"):
        f.abono(cliente, [(cargo, 25000)], sesion_id=s)
    sql = "INSERT INTO condonaciones_credito (cargo_id, monto, motivo, autorizada_por) VALUES (%s, %s, 'Error de cobro', %s)"
    db.execute(sql, (cargo, 20000, f.usuario("admin")))
    confirmar(db)
    assert _cargo(db, cargo) == {"abonado": Decimal("30000"), "condonado": Decimal("20000"),
                                 "pendiente": 0, "vencido": False}
    with falla(db, "pagado de más"):
        db.execute(sql, (cargo, 1, f.usuario("admin")))


def test_cargo_vencido(db, f):
    cliente = f.cliente()
    cargo = f.cargo(cliente, 1000, vence_en="2020-01-01")
    assert _cargo(db, cargo)["vencido"] is True


def test_cruce_de_nomina_contra_fiado(db, f):
    # Saavedra es empleado y cliente: se le paga la nómina en parte por
    # transferencia y en parte descontándole su deuda.
    s = f.turno(base_digital=500000)
    saavedra = f.cliente()
    deuda = f.cargo(saavedra, 119500)
    nomina = f.gasto(s, [("transferencia", 180500)], categoria="Nómina", tercero_id=saavedra)
    f.abono(saavedra, [(deuda, 119500)], egreso_id=nomina)
    confirmar(db)
    egreso = db.execute("SELECT pagado, cruzado, monto FROM v_egresos WHERE id = %s", (nomina,)).fetchone()
    assert egreso == {"pagado": Decimal("180500"), "cruzado": Decimal("119500"), "monto": Decimal("300000")}
    assert _cargo(db, deuda)["pendiente"] == 0
    # El cruce no mueve plata de ninguna caja: solo salió la transferencia.
    digital = db.execute("SELECT esperado FROM v_sesion_cajas WHERE sesion_id = %s AND caja = 'Digital'",
                         (s,)).fetchone()["esperado"]
    assert digital == Decimal("319500")

    # Anular la nómina hace que el cruce deje de contar: la deuda vuelve.
    db.execute("INSERT INTO anulaciones_egreso (egreso_id, sesion_id, usuario_id, motivo) "
               "VALUES (%s, %s, %s, 'Registro duplicado')", (nomina, s, f.usuario()))
    assert _cargo(db, deuda)["pendiente"] == Decimal("119500")


def test_cruce_solo_con_el_mismo_tercero(db, f):
    s, saavedra, otro = f.turno(), f.cliente(), f.cliente()
    deuda = f.cargo(saavedra, 10000)
    gasto_otro = f.gasto(s, [("efectivo", 1000)], categoria="Nómina", tercero_id=otro)
    with falla(db, "Cruce de cuentas inválido"):
        f.abono(saavedra, [(deuda, 10000)], egreso_id=gasto_otro)


def test_abono_con_plata_o_con_cruce(db, f):
    s, cliente = f.turno(), f.cliente()
    with falla(db, "abonos_credito_plata_o_cruce"):
        db.execute("INSERT INTO abonos_credito (cliente_id, sesion_id, usuario_id, monto) VALUES (%s, %s, %s, 1)",
                   (cliente, s, f.usuario()))


# ── Compras y gastos ────────────────────────────────────────────────────────

def test_compra_soporte_y_lineas(db, f):
    prov = f.proveedor()
    with falla(db, "compras_fe_con_cufe"):
        f.compra(prov, [], tipo_soporte="factura_electronica", numero_soporte="FE1")
    f.compra(prov, [], tipo_soporte="factura", numero_soporte="30524")
    with falla(db, "compras_soporte_unico"):
        f.compra(prov, [], tipo_soporte="factura", numero_soporte="30524")
    f.compra(prov, [])
    f.compra(prov, [])  # sin número de soporte: no choca
    with falla(db, "compra_lineas_producto_o_insumo"):
        f.compra(prov, [(f.producto(), f.insumo(), 1, 100)])


def test_pago_de_compra_y_cuenta_por_pagar(db, f):
    s, prov = f.turno(base_efectivo=1000000), f.proveedor()
    compra = f.compra(prov, [(f.producto(), None, 10, 9000), (None, f.insumo(), 2000, 12.5)])
    f.pago_compra(s, compra, [("efectivo", 50000), ("nequi", 40000)])
    confirmar(db)
    fila = db.execute("SELECT total, pagado, pendiente FROM v_compras WHERE id = %s", (compra,)).fetchone()
    assert fila == {"total": Decimal("115000.00"), "pagado": Decimal("90000"), "pendiente": Decimal("25000.00")}
    with falla(db, "se le pagaría"):
        f.pago_compra(s, compra, [("efectivo", 30000)])


def test_egreso_compra_o_gasto_y_con_pagos(db, f):
    s = f.turno()
    with falla(db, "egresos_compra_o_gasto"):
        db.execute("INSERT INTO egresos (sesion_id, usuario_id, concepto) VALUES (%s, %s, 'x')", (s, f.usuario()))
    with falla(db, "no tiene pagos ni cruces"):
        f.gasto(s, [])


def test_egresos_solo_insercion(db, f):
    s = f.turno()
    gasto = f.gasto(s, [("efectivo", 5000)])
    confirmar(db)
    with falla(db, "solo inserción"):
        db.execute("DELETE FROM egresos WHERE id = %s", (gasto,))
