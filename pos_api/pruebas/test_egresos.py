"""Egresos: gastos, nómina con cruce de cuentas, pagos de compra y anulación."""
import uuid

import pytest


def _esperado(bd, turno, caja="Efectivo"):
    return bd.execute(
        """SELECT esperado FROM v_sesion_cajas vs JOIN cajas c ON c.id = vs.caja_id
            WHERE vs.sesion_id = %s AND c.nombre = %s""", (turno, caja)).fetchone()["esperado"]


def _saldo(bd, cliente):
    return bd.execute("SELECT saldo FROM v_saldos_clientes WHERE cliente_id = %s", (cliente,)).fetchone()["saldo"]


@pytest.fixture
def categoria(f):
    return lambda nombre="Otros": str(f.id_de("categorias_gasto", "nombre", nombre))


def test_gasto(api, sesion, bd, f, turno, categoria):
    h = sesion("vendedor")
    efectivo = str(f.metodo("efectivo"))
    antes = _esperado(bd, turno)
    gastar = lambda **body: api.post("/egresos", headers=h, json={"sesion_id": str(turno), "concepto": "Hielo",
                                                                  "categoria_gasto_id": categoria(), **body})
    r = gastar(pagos=[{"metodo_pago_id": efectivo, "monto": 4000}], notas="Dos bolsas")
    assert r.status_code == 201, r.text
    gasto = r.json()
    assert (gasto["tipo"], gasto["monto"], gasto["categoria"], gasto["metodos"], gasto["anulado"]) == \
        ("gasto", 4000, "Otros", "Efectivo", False)
    assert gasto["pagos"] == [{"metodo": "Efectivo", "caja": "Efectivo", "monto": 4000}]
    assert antes - _esperado(bd, turno) == 4000
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s", (gasto["id"],)).fetchone()["detalle"]
    assert detalle.startswith("Gasto de $4.000 (Otros): Hielo en el turno #") and detalle.endswith("(Efectivo $4.000)")
    assert any(e["id"] == gasto["id"] for e in api.get("/egresos", headers=h, params={"tipo": "gasto"}).json())
    assert all(e["id"] != gasto["id"] for e in api.get("/egresos", headers=h, params={"tipo": "compra"}).json())

    r = gastar()
    assert (r.status_code, r.json()["detail"]) == (400, "Indica cuánto se paga.")
    r = gastar(categoria_gasto_id=None, pagos=[{"metodo_pago_id": efectivo, "monto": 1}])
    assert r.status_code == 400 and "gasto con categoría o el pago de una compra" in r.json()["detail"]
    r = gastar(categoria_gasto_id=str(uuid.uuid4()), pagos=[{"metodo_pago_id": efectivo, "monto": 1}])
    assert (r.status_code, r.json()["detail"]) == (404, "La categoría de gasto no existe.")
    r = gastar(tercero_id=str(uuid.uuid4()), pagos=[{"metodo_pago_id": efectivo, "monto": 1}])
    assert r.status_code == 404
    r = gastar(concepto=" ", pagos=[{"metodo_pago_id": efectivo, "monto": 1}])
    assert r.status_code == 422
    r = gastar(sesion_id=str(uuid.uuid4()), pagos=[{"metodo_pago_id": efectivo, "monto": 1}])
    assert (r.status_code, r.json()["detail"]) == (404, "El turno de caja no existe.")
    assert api.get(f"/egresos/{uuid.uuid4()}", headers=h).status_code == 404


def test_nomina_con_cruce_de_cuentas(api, sesion, bd, f, turno, categoria):
    h, vendedor = sesion("admin"), sesion("vendedor")
    empleado = f.cliente()
    f.cargo(empleado, 30000, notas="Fiado del mes")
    efectivo = str(f.metodo("efectivo"))
    pagar = lambda **body: api.post("/egresos", headers=h, json={
        "sesion_id": str(turno), "concepto": "Quincena", "categoria_gasto_id": categoria("Nómina"),
        "tercero_id": str(empleado), **body})

    # Cruzar baja una deuda sin que entre plata: exige el permiso de condonar.
    r = api.post("/egresos", headers=vendedor, json={
        "sesion_id": str(turno), "concepto": "Quincena", "categoria_gasto_id": categoria("Nómina"),
        "tercero_id": str(empleado), "cruce": 30000})
    assert r.status_code == 403 and "permiso de condonar" in r.json()["detail"]
    r = pagar(pagos=[{"metodo_pago_id": efectivo, "monto": 1}], cruce=40000)
    assert r.status_code == 400 and "supera lo que debe" in r.json()["detail"]
    r = pagar(pagos=[{"metodo_pago_id": efectivo, "monto": 20000}], cruce=30000)
    assert r.status_code == 201, r.text
    nomina = r.json()
    assert (nomina["monto"], nomina["pagado"], nomina["cruzado"], nomina["beneficiario_id"]) == (50000, 20000, 30000, str(empleado))
    assert _saldo(bd, empleado) == 0
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s", (nomina["id"],)).fetchone()["detalle"]
    assert "cruce $30.000 contra su fiado (queda debiendo $0)" in detalle

    # Sin a quién, o a alguien que no es cliente, no hay cruce.
    r = api.post("/egresos", headers=h, json={"sesion_id": str(turno), "concepto": "x", "categoria_gasto_id": categoria(),
                                              "cruce": 1000})
    assert (r.status_code, r.json()["detail"]) == (400, "Para cruzar cuentas indica a quién se le paga.")
    r = pagar(tercero_id=str(f.tercero()), cruce=1000)
    assert r.status_code == 400 and "no es cliente" in r.json()["detail"]
    r = pagar(cruce=1000)
    assert r.status_code == 400 and r.json()["detail"].endswith("no debe nada.")


def test_pago_de_compra(api, sesion, bd, f, turno):
    admin, vendedor = sesion("admin"), sesion("vendedor")
    proveedor = f.cliente()  # también le compramos fiado: se cruza
    f.proveedor(tercero_id=proveedor)
    f.cargo(proveedor, 5000, notas="Le fiamos")
    with bd.transaction():
        pid = f.producto()
    compra = api.post("/compras", headers=admin, json={"proveedor_id": str(proveedor), "lineas": [
        {"producto_id": str(pid), "cantidad": 10, "costo_unit": 1850}]}).json()
    efectivo = str(f.metodo("efectivo"))
    pagar = lambda h=admin, **body: api.post("/egresos", headers=h, json={
        "sesion_id": str(turno), "concepto": f"Pago compra #{compra['numero']}", "compra_id": compra["id"], **body})

    assert pagar(vendedor, pagos=[{"metodo_pago_id": efectivo, "monto": 1000}]).status_code == 403
    assert pagar(pagos=[{"metodo_pago_id": efectivo, "monto": 10000}]).status_code == 201
    r = pagar(pagos=[{"metodo_pago_id": efectivo, "monto": 9000}])
    assert r.status_code == 400 and "le quedan $8.500 por pagar" in r.json()["detail"]
    r = pagar(pagos=[{"metodo_pago_id": efectivo, "monto": 1}], tercero_id=str(f.tercero()))
    assert r.status_code == 201 and r.json()["beneficiario_id"] == str(proveedor)  # el de la compra, no otro
    r = pagar(pagos=[{"metodo_pago_id": efectivo, "monto": 3499}], cruce=5000)
    assert r.status_code == 201, r.text
    detalle = api.get(f"/compras/{compra['id']}", headers=admin).json()
    assert (detalle["pagado"], detalle["pendiente"], len(detalle["pagos"])) == (18500, 0, 3)
    assert _saldo(bd, proveedor) == 0
    r = pagar(pagos=[{"metodo_pago_id": efectivo, "monto": 1}])
    assert r.status_code == 400 and "ya está pagada" in r.json()["detail"]
    assert pagar(categoria_gasto_id=str(f.id_de("categorias_gasto", "nombre", "Otros")),
                 pagos=[{"metodo_pago_id": efectivo, "monto": 1}]).status_code == 400
    r = api.post("/egresos", headers=admin, json={"sesion_id": str(turno), "concepto": "x", "compra_id": str(uuid.uuid4()),
                                                  "pagos": [{"metodo_pago_id": efectivo, "monto": 1}]})
    assert (r.status_code, r.json()["detail"]) == (404, "La compra no existe.")


def test_anular(api, sesion, bd, f, turno, categoria):
    admin, vendedor = sesion("admin"), sesion("vendedor")
    efectivo = str(f.metodo("efectivo"))
    empleado = f.cliente()
    f.cargo(empleado, 8000, notas="Fiado")
    gasto = api.post("/egresos", headers=admin, json={
        "sesion_id": str(turno), "concepto": "Adelanto", "categoria_gasto_id": categoria("Nómina"),
        "tercero_id": str(empleado), "pagos": [{"metodo_pago_id": efectivo, "monto": 12000}], "cruce": 8000}).json()
    antes = _esperado(bd, turno)
    anular = lambda h=admin, **body: api.post(f"/egresos/{gasto['id']}/anular", headers=h,
                                              json={"sesion_id": str(turno), "motivo": "Se registró dos veces", **body})

    assert anular(vendedor).status_code == 403
    assert anular(motivo=" ").status_code == 422
    r = anular()
    assert r.status_code == 200, r.text
    anulado = r.json()
    assert (anulado["anulado"], anulado["motivo_anulacion"]) == (True, "Se registró dos veces") and anulado["anulado_por"]
    # La plata vuelve a la caja y el cruce deja de contar: la deuda reaparece.
    assert _esperado(bd, turno) - antes == 12000
    assert _saldo(bd, empleado) == 8000
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s ORDER BY id DESC LIMIT 1",
                         (gasto["id"],)).fetchone()["detalle"]
    assert detalle.startswith("Anuló el gasto «Adelanto» por $20.000; vuelven $12.000 a caja en el turno #")
    assert "el cruce de $8.000 deja de contar: Se registró dos veces" in detalle

    r = anular()
    assert (r.status_code, r.json()["detail"]) == (400, "Ese egreso ya está anulado.")
    assert api.post(f"/egresos/{uuid.uuid4()}/anular", headers=admin,
                    json={"sesion_id": str(turno), "motivo": "x"}).status_code == 404


def test_anular_pago_de_compra_reabre_la_deuda(api, sesion, f, turno):
    admin = sesion("admin")
    proveedor = f.proveedor()
    insumo = str(f.insumo())
    compra = api.post("/compras", headers=admin, json={"proveedor_id": str(proveedor), "lineas": [
        {"insumo_id": insumo, "cantidad": 2, "costo_unit": 5000}]}).json()
    pago = api.post("/egresos", headers=admin, json={
        "sesion_id": str(turno), "concepto": "Pago", "compra_id": compra["id"],
        "pagos": [{"metodo_pago_id": str(f.metodo("nequi")), "monto": 10000}]}).json()
    assert api.get(f"/compras/{compra['id']}", headers=admin).json()["pendiente"] == 0
    r = api.post(f"/egresos/{pago['id']}/anular", headers=admin, json={"sesion_id": str(turno), "motivo": "Error"})
    assert r.status_code == 200, r.text
    detalle = api.get(f"/compras/{compra['id']}", headers=admin).json()
    assert (detalle["pendiente"], detalle["pagos"][0]["anulado"]) == (10000, True)


def test_sin_reportes_solo_el_turno_abierto(api, sesion, f, categoria):
    from pos_api.pruebas.test_caja import _abrir
    admin, vendedor = sesion("admin"), sesion("vendedor")
    turno = _abrir(api, admin)
    efectivo = str(f.metodo("efectivo"))
    gastar = lambda sid: api.post("/egresos", headers=vendedor, json={
        "sesion_id": sid, "concepto": "Hielo", "categoria_gasto_id": categoria(),
        "pagos": [{"metodo_pago_id": efectivo, "monto": 1000}]}).json()
    viejo = gastar(turno["id"])
    nuevo_turno = _abrir(api, admin)  # cierra el anterior
    nuevo = gastar(nuevo_turno["id"])

    ids = [e["id"] for e in api.get("/egresos", headers=vendedor, params={"desde": "2000-01-01"}).json()]
    assert nuevo["id"] in ids and viejo["id"] not in ids
    r = api.get(f"/egresos/{viejo['id']}", headers=vendedor)
    assert (r.status_code, r.json()["detail"]) == (403, "Solo puedes ver los egresos del turno abierto.")
    assert api.get(f"/egresos/{nuevo['id']}", headers=vendedor).status_code == 200
    # Con reportes.ver se ve todo.
    ids = [e["id"] for e in api.get("/egresos", headers=admin, params={"desde": "2000-01-01"}).json()]
    assert viejo["id"] in ids and nuevo["id"] in ids
    assert api.get(f"/egresos/{viejo['id']}", headers=admin).status_code == 200
