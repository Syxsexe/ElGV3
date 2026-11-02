"""Grupos 9 y 10: documentos fiscales y comerciales, y torneos."""
from decimal import Decimal

from ayudas import confirmar, falla


def _resolucion(db, tipo):
    return db.execute(
        "INSERT INTO resoluciones (tipo_documento, prefijo, rango_inicio, rango_fin, consecutivo_actual, "
        "fecha_autorizacion, fecha_vencimiento) VALUES (%s, %s, 1, 1000, 0, '2026-01-01', '2028-01-01') "
        "RETURNING id", (tipo, tipo)).fetchone()["id"]


def _fiscal(db, f, tipo, venta=None, referencia=None, estado="local", motivo=None, resolucion=None):
    """Un documento solo local (prefijo LOC) salvo que se pase una resolución."""
    f._n += 1
    prefijo = "LOC" if resolucion is None else tipo
    return db.execute(
        "INSERT INTO documentos_fiscales (tipo, resolucion_id, prefijo, consecutivo, venta_id, "
        "documento_referencia_id, adquiriente_id, adq_nombre, estado, motivo) "
        "SELECT %s, %s, %s, %s, %s, %s, id, nombre, %s, %s FROM terceros WHERE nombre = 'CONSUMIDOR FINAL' "
        "RETURNING id",
        (tipo, resolucion, prefijo, f._n, venta, referencia, estado, motivo)).fetchone()["id"]


def test_una_factura_vigente_por_venta(db, f):
    s, prod = f.turno(), f.producto(precio=5000)
    v = f.venta(s, [(prod, 1, 5000)], pagos=[("efectivo", 5000)])
    fev = _fiscal(db, f, "FEV", venta=v)
    with falla(db, "ya tiene un documento fiscal vigente"):
        _fiscal(db, f, "FEV", venta=v)
    # Se corrige con nota crédito aceptada y se reemite para la misma venta.
    nc = _fiscal(db, f, "NC", referencia=fev, estado="aceptado", motivo="NIT equivocado",
                 resolucion=_resolucion(db, "NC"))
    _fiscal(db, f, "FEV", venta=v)
    confirmar(db)
    filas = db.execute("SELECT id, anulado, total FROM v_documentos_fiscales WHERE id IN (%s, %s)",
                       (fev, nc)).fetchall()
    assert {r["id"]: (r["anulado"], r["total"]) for r in filas} == {
        fev: (True, Decimal("5000.00")), nc: (False, Decimal("5000.00"))}
    with falla(db, "no otra nota crédito"):
        _fiscal(db, f, "NC", referencia=nc, motivo="x")


def test_documento_fiscal_segun_tipo_y_resolucion(db, f):
    with falla(db, "documentos_fiscales_segun_tipo"):
        _fiscal(db, f, "FEV")
    with falla(db, "documentos_fiscales_local_sin_resolucion"):
        s, prod = f.turno(), f.producto(precio=1)
        v = f.venta(s, [(prod, 1, 1)], pagos=[("efectivo", 1)])
        _fiscal(db, f, "POS", venta=v, estado="pendiente")


def _comercial(db, f, tipo, origen=None, **extra):
    doc = db.execute(
        "INSERT INTO documentos_comerciales (tipo, usuario_id, doc_origen_id, vigente_hasta) "
        "VALUES (%s, %s, %s, %s) RETURNING id, numero",
        (tipo, f.usuario(), origen, extra.get("vigente_hasta"))).fetchone()
    return doc["id"], doc["numero"]


def _estado(db, doc):
    return db.execute("SELECT estado FROM v_documentos_comerciales WHERE id = %s", (doc,)).fetchone()["estado"]


def test_cadena_de_documentos_comerciales(db, f):
    cot, n1 = _comercial(db, f, "cotizacion", vigente_hasta="2099-01-01")
    cot2, n2 = _comercial(db, f, "cotizacion")
    assert n2 == n1 + 1  # consecutivo propio del tipo
    assert _estado(db, cot) == "vigente"
    orden, _ = _comercial(db, f, "orden_pedido", origen=cot)
    assert _estado(db, cot) == "aceptada"
    _comercial(db, f, "remision", origen=orden)
    assert _estado(db, orden) == "entregada"
    with falla(db, "la cadena es"):
        _comercial(db, f, "remision", origen=cot2)
    with falla(db, "vigencia_solo_cotizacion"):
        _comercial(db, f, "orden_pedido", vigente_hasta="2099-01-01")
    vieja, _ = _comercial(db, f, "cotizacion", vigente_hasta="2020-01-01")
    assert _estado(db, vieja) == "vencida"
    db.execute("UPDATE documentos_comerciales SET descartado_en = now(), motivo_descarte = 'rechazado' "
               "WHERE id = %s", (cot2,))
    assert _estado(db, cot2) == "rechazada"


# ── Torneos ─────────────────────────────────────────────────────────────────

def test_torneo_con_pago_fiado_y_gratis(db, f):
    s = f.turno()
    carlos, sebastian = f.cliente(), f.cliente()
    insc = f.inscripcion()
    # Pagan 2 jugadores (efectivo y fiado); un tercero entra gratis.
    v = f.venta(s, [(insc, 2, 15000)])
    pago = f.pago_venta(v, "efectivo", 15000)
    cargo = f.cargo(sebastian, 15000, venta_id=v)
    sobre = f.producto(precio=20000, costo=11050)
    t = db.execute("INSERT INTO torneos (nombre, juego_id, usuario_id, venta_id) "
                   "SELECT 'Yugi Semanal', id, %s, %s FROM juegos WHERE nombre = 'Yu-Gi-Oh!' RETURNING id",
                   (f.usuario(), v)).fetchone()["id"]
    sql = "INSERT INTO torneo_participantes (torneo_id, cliente_id, alias, pago_venta_id, cargo_id) VALUES (%s, %s, %s, %s, %s)"
    db.execute(sql, (t, carlos, None, pago, None))
    db.execute(sql, (t, sebastian, None, None, cargo))
    db.execute(sql, (t, None, "Byron", None, None))
    db.execute("INSERT INTO torneo_premios VALUES (%s, %s, 2, 11050)", (t, sobre))
    confirmar(db)
    fila = db.execute("SELECT recaudado, costo_premios, ganancia, jugadores, jugadores_gratis "
                      "FROM v_torneos WHERE id = %s", (t,)).fetchone()
    assert fila == {"recaudado": Decimal("30000.00"), "costo_premios": Decimal("22100.00"),
                    "ganancia": Decimal("7900.00"), "jugadores": 3, "jugadores_gratis": 1}
    with falla(db, "torneo_participantes_una_inscripcion"):
        db.execute(sql, (t, carlos, None, None, None))


def test_participante_con_pago_de_otra_venta(db, f):
    s, insc, prod = f.turno(), f.inscripcion(), f.producto(precio=1000)
    otra = f.venta(s, [(prod, 1, 1000)])
    pago_ajeno = f.pago_venta(otra, "efectivo", 1000)
    t = db.execute("INSERT INTO torneos (nombre, juego_id, usuario_id) "
                   "SELECT 'Torneo', id, %s FROM juegos LIMIT 1 RETURNING id", (f.usuario(),)).fetchone()["id"]
    with falla(db, "no pertenece a la venta del torneo"):
        db.execute("INSERT INTO torneo_participantes (torneo_id, alias, pago_venta_id) VALUES (%s, 'X', %s)",
                   (t, pago_ajeno))
    with falla(db, "torneo_participantes_fiado_con_cliente"):
        db.execute("INSERT INTO torneo_participantes (torneo_id, alias, cargo_id) VALUES (%s, 'X', %s)",
                   (t, f.cargo(f.cliente(), 1000)))
    assert insc
