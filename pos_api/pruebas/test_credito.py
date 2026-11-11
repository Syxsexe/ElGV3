"""Crédito: saldos, abonos (orden automático o elegido), cargos manuales y condonaciones."""
import datetime
import uuid


def _hoy(bd):
    return bd.execute("SELECT current_date AS hoy").fetchone()["hoy"]


def _esperado(bd, turno, caja):
    return bd.execute(
        """SELECT esperado FROM v_sesion_cajas vs JOIN cajas c ON c.id = vs.caja_id
            WHERE vs.sesion_id = %s AND c.nombre = %s""", (turno, caja)).fetchone()["esperado"]


def test_abono_paga_primero_lo_que_vence_antes(api, sesion, bd, f, turno):
    h = sesion("vendedor")
    cliente = f.cliente(limite=100000)
    tarde = f.cargo(cliente, 10000, notas="Saldo anterior", vence_en="2099-01-10")
    pronto = f.cargo(cliente, 5000, notas="Préstamo", vence_en="2099-01-05")
    antes = _esperado(bd, turno, "Efectivo")
    efectivo = str(f.metodo("efectivo"))
    abonar = lambda **body: api.post(f"/creditos/{cliente}/abonos", headers=h,
                                     json={"sesion_id": str(turno), "metodo_pago_id": efectivo, **body})

    r = abonar(monto=16000)
    assert r.status_code == 400 and "supera lo que debe" in r.json()["detail"] and "($15.000)" in r.json()["detail"]
    r = abonar(monto=8000, notas="Pagó la mitad")
    assert r.status_code == 201, r.text
    cargos = {c["id"]: c for c in r.json()["cargos"]}
    assert (cargos[str(pronto)]["pendiente"], cargos[str(tarde)]["pendiente"]) == (0, 7000)
    # Pendientes primero; el pagado al final.
    assert [c["id"] for c in r.json()["cargos"]] == [str(tarde), str(pronto)]
    abono = r.json()["abonos"][0]
    assert (abono["monto"], abono["metodo"], abono["cargos"], abono["notas"]) == (8000, "Efectivo", 2, "Pagó la mitad")
    assert r.json()["cliente"]["saldo"] == 7000
    assert _esperado(bd, turno, "Efectivo") - antes == 8000
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad = 'abonos_credito' ORDER BY id DESC LIMIT 1"
                         ).fetchone()["detalle"]
    assert detalle.startswith("Abono de $8.000 de") and "aplicado a 2 cargo(s); queda debiendo $7.000" in detalle

    assert abonar(monto=7000).status_code == 201
    r = abonar(monto=1)
    assert r.status_code == 400 and r.json()["detail"].endswith("no debe nada.")
    r = abonar(monto=1, metodo_pago_id=str(uuid.uuid4()))
    assert r.status_code == 400
    assert abonar(monto=0).status_code == 422
    r = api.post(f"/creditos/{uuid.uuid4()}/abonos", headers=h,
                 json={"sesion_id": str(turno), "metodo_pago_id": efectivo, "monto": 1})
    assert (r.status_code, r.json()["detail"]) == (404, "El cliente no existe.")
    r = abonar(monto=1, sesion_id=str(uuid.uuid4()))
    assert (r.status_code, r.json()["detail"]) == (404, "El turno de caja no existe.")


def test_abono_a_cargos_elegidos(api, sesion, bd, f, turno):
    h = sesion("vendedor")
    cliente, otro = f.cliente(), f.cliente()
    viejo = str(f.cargo(cliente, 10000, vence_en="2099-01-01"))
    nuevo = str(f.cargo(cliente, 6000, vence_en="2099-02-01"))
    ajeno = str(f.cargo(otro, 3000))
    nequi = str(f.metodo("nequi"))
    abonar = lambda monto, aplicaciones: api.post(f"/creditos/{cliente}/abonos", headers=h, json={
        "sesion_id": str(turno), "metodo_pago_id": nequi, "monto": monto,
        "aplicaciones": [{"cargo_id": c, "monto": m} for c, m in aplicaciones]})

    r = abonar(5000, [(nuevo, 4000)])
    assert r.status_code == 400 and "no es igual al abono" in r.json()["detail"]
    r = abonar(7000, [(nuevo, 7000)])
    assert r.status_code == 400 and "solo le quedan $6.000" in r.json()["detail"]
    r = abonar(3000, [(ajeno, 3000)])
    assert r.status_code == 400 and "no es de este cliente" in r.json()["detail"]
    r = abonar(2000, [(nuevo, 1000), (nuevo, 1000)])
    assert r.status_code == 400 and "dos veces" in r.json()["detail"]

    # Paga el más nuevo aunque el viejo venza antes.
    r = abonar(6000, [(nuevo, 6000)])
    assert r.status_code == 201, r.text
    pendientes = {c["id"]: c["pendiente"] for c in r.json()["cargos"]}
    assert (pendientes[viejo], pendientes[nuevo]) == (10000, 0)
    assert bd.execute("SELECT count(*) AS n FROM abonos_credito WHERE cliente_id = %s", (cliente,)).fetchone()["n"] == 1


def test_cargo_manual(api, sesion, bd, f):
    vendedor, admin = sesion("vendedor"), sesion("admin")
    cliente = f.cliente(limite=0)
    bd.execute("UPDATE clientes SET dias_credito = 10 WHERE tercero_id = %s", (cliente,))
    cargo = {"monto": 25000, "notas": "Saldo del sistema anterior"}
    assert api.post(f"/creditos/{cliente}/cargos", headers=vendedor, json=cargo).status_code == 403

    # No revisa el cupo (este cliente no tiene) y vence según sus días de crédito.
    r = api.post(f"/creditos/{cliente}/cargos", headers=admin, json=cargo)
    assert r.status_code == 201, r.text
    c = r.json()["cargos"][0]
    assert (c["monto"], c["notas"], c["vence_en"]) == (25000, "Saldo del sistema anterior",
                                                      str(_hoy(bd) + datetime.timedelta(days=10)))
    # Con fecha pasada queda vencido.
    r = api.post(f"/creditos/{cliente}/cargos", headers=admin, json={"monto": 1000, "notas": "Viejo", "vence_en": "2020-01-01"})
    assert r.json()["cliente"]["cargos_vencidos"] == 1 and r.json()["cliente"]["vencido"] == 1000
    assert api.post(f"/creditos/{cliente}/cargos", headers=admin, json={"monto": 1000, "notas": "  "}).status_code == 422
    assert api.post(f"/creditos/{uuid.uuid4()}/cargos", headers=admin, json=cargo).status_code == 404
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad = 'cargos_credito' AND entidad_id = %s",
                         (c["id"],)).fetchone()["detalle"]
    assert detalle.startswith("Cargó $25.000 a") and detalle.endswith(": Saldo del sistema anterior")


def test_condonar(api, sesion, bd, f, turno):
    vendedor, admin = sesion("vendedor"), sesion("admin")
    cliente = f.cliente()
    cargo = str(f.cargo(cliente, 9000, notas="Préstamo"))
    with bd.transaction():  # el abono y su aplicación cuadran al confirmar
        f.abono(cliente, [(cargo, 4000)], sesion_id=turno)
    condonar = lambda h, **body: api.post(f"/creditos/cargos/{cargo}/condonar", headers=h, json=body)

    assert condonar(vendedor, monto=1000, motivo="x").status_code == 403
    r = condonar(admin, monto=6000, motivo="Error de digitación")
    assert (r.status_code, r.json()["detail"]) == (400, "Al cargo solo le quedan $5.000 por pagar.")
    assert condonar(admin, monto=1000, motivo=" ").status_code == 422
    r = condonar(admin, monto=2000, motivo="Descuento por cliente frecuente")
    assert r.status_code == 201, r.text
    c = next(x for x in r.json()["cargos"] if x["id"] == cargo)
    assert (c["abonado"], c["condonado"], c["pendiente"]) == (4000, 2000, 3000)
    assert r.json()["condonaciones"][0]["motivo"] == "Descuento por cliente frecuente"
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s ORDER BY id DESC LIMIT 1",
                         (cargo,)).fetchone()["detalle"]
    assert detalle.startswith("Condonó $2.000 a") and "del cargo de $9.000 (Préstamo)" in detalle

    assert condonar(admin, monto=3000, motivo="Saldo perdido").status_code == 201
    r = condonar(admin, monto=1, motivo="x")
    assert r.status_code == 400 and "ya está pagado" in r.json()["detail"]
    assert api.post(f"/creditos/cargos/{uuid.uuid4()}/condonar", headers=admin,
                    json={"monto": 1, "motivo": "x"}).status_code == 404


def test_listar_saldos(api, sesion, bd, f):
    h = sesion("vendedor")
    debe = f.cliente()
    f.cargo(debe, 12000, notas="Saldo", vence_en="2020-01-01")
    nombre_sin_deuda = f"Sin deuda {uuid.uuid4().hex[:6]}"
    sin_deuda = f.cliente(tercero_id=f.tercero(nombre=nombre_sin_deuda))

    r = api.get("/creditos", headers=h).json()
    ids = [c["cliente_id"] for c in r["clientes"]]
    assert str(debe) in ids and str(sin_deuda) not in ids
    assert all(c["saldo"] > 0 for c in r["clientes"])
    # Los que tienen deuda vencida van primero.
    vencidos = [c["cargos_vencidos"] > 0 for c in r["clientes"]]
    assert vencidos == sorted(vencidos, reverse=True)
    assert r["cartera"]["total"] >= 12000 and r["cartera"]["vencido"] >= 12000

    # Buscando aparece aunque no deba (para abonarle o cargarle).
    r = api.get("/creditos", headers=h, params={"q": nombre_sin_deuda}).json()
    assert [c["cliente_id"] for c in r["clientes"]] == [str(sin_deuda)]
    assert r["clientes"][0]["saldo"] == 0
    assert r["cartera"] is None  # los totales no dependen de la búsqueda

    detalle = api.get(f"/creditos/{debe}", headers=h).json()
    assert (detalle["cliente"]["saldo"], detalle["cliente"]["vencido"], len(detalle["cargos"])) == (12000, 12000, 1)
    assert detalle["cargos"][0]["vencido"] is True
    assert detalle["totales"] == {"cargos_pagados": 0, "abonos": 0, "condonaciones": 0}
    assert api.get(f"/creditos/{uuid.uuid4()}", headers=h).status_code == 404
    assert api.get("/creditos").status_code == 401
