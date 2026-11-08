"""Turnos de caja: apertura, movimientos, cierre e historial.

La base de prueba es compartida y solo admite un turno abierto: cada prueba
empieza cerrando el que haya (_sin_turno) y abre el suyo por la API.
"""
import uuid

import pytest


def _sin_turno(api, h):
    """Cierra el turno abierto (si hay) contando todo en cero."""
    turno = api.get("/caja/turno", headers=h).json()["turno"]
    if turno:
        contados = {c["caja_id"]: 0 for c in turno["cajas"] if not c["usa_denominaciones"]}
        r = api.post(f"/caja/turnos/{turno['id']}/cerrar", headers=h, json={"contados": contados})
        assert r.status_code == 200, r.text


def _abrir(api, h, **bases_por_nombre):
    """Abre un turno con base 0 en las cajas activas que no se nombren."""
    _sin_turno(api, h)
    cajas = api.get("/caja/turno", headers=h).json()["cajas"]
    bases = {c["id"]: bases_por_nombre.get(c["nombre"], 0) for c in cajas}
    r = api.post("/caja/turnos", headers=h, json={"bases": bases})
    assert r.status_code == 201, r.text
    return r.json()


def _caja(turno, nombre):
    return next(c for c in turno["cajas"] if c["caja"] == nombre)


@pytest.fixture
def denominacion(api):
    def _id(h, valor):
        return next(d["id"] for d in api.get("/caja/denominaciones", headers=h).json() if d["valor"] == valor)
    return _id


def test_turno_completo(api, sesion, f, bd, denominacion):
    h = sesion("vendedor")
    turno = _abrir(api, h, Efectivo=50000, Digital=10000)
    efectivo, digital = _caja(turno, "Efectivo")["caja_id"], _caja(turno, "Digital")["caja_id"]
    assert turno["abierta_por"] and turno["cerrada_en"] is None

    otro = api.post("/caja/turnos", headers=h, json={"bases": {efectivo: 0, digital: 0}})
    assert (otro.status_code, otro.json()["detail"]) == (400, "Ya hay un turno de caja abierto.")

    with bd.transaction():
        f.venta(turno["id"], [(f.producto(precio=25000), 1, 25000)], pagos=[("efectivo", 20000), ("nequi", 5000)])
    movimientos = [
        {"tipo": "retiro", "caja_origen_id": efectivo, "monto": 3000, "motivo": "Hielo"},
        {"tipo": "traslado", "caja_origen_id": efectivo, "caja_destino_id": digital, "monto": 10000, "motivo": "Consignación"},
        {"tipo": "ingreso", "caja_destino_id": digital, "monto": 1000, "motivo": "Devolución proveedor"},
    ]
    for m in movimientos:
        r = api.post(f"/caja/turnos/{turno['id']}/movimientos", headers=h, json=m)
        assert r.status_code == 201, r.text
    mover = lambda body: api.post(f"/caja/turnos/{turno['id']}/movimientos", headers=h, json=body)
    malo = mover({
        "tipo": "traslado", "caja_origen_id": efectivo, "caja_destino_id": efectivo, "monto": 1, "motivo": "x"})
    assert malo.status_code == 400 and "de una caja a otra distinta" in malo.json()["detail"]
    assert mover({**movimientos[0], "motivo": "  "}).status_code == 422
    r = mover({**movimientos[0], "caja_origen_id": str(uuid.uuid4())})
    assert (r.status_code, r.json()["detail"]) == (404, "La caja indicada no existe.")

    turno = api.get("/caja/turno", headers=h).json()["turno"]
    ef, dig = _caja(turno, "Efectivo"), _caja(turno, "Digital")
    # Efectivo: 50.000 + 20.000 − 3.000 − 10.000; Digital: 10.000 + 5.000 + 10.000 + 1.000.
    assert (ef["esperado"], dig["esperado"]) == (57000, 26000)
    assert ef["flujos"] == {"venta": 20000, "retiro": -3000, "traslado_salida": -10000}
    assert dig["flujos"] == {"venta": 5000, "traslado_entrada": 10000, "ingreso": 1000}
    for c in turno["cajas"]:  # el desglose siempre suma el esperado
        assert c["base"] + sum(c["flujos"].values()) == c["esperado"]
    assert (turno["ventas"]["cantidad"], turno["ventas"]["total"]) == (1, 25000)
    assert [m["tipo"] for m in turno["movimientos"]] == ["retiro", "traslado", "ingreso"]

    # La caja de billetes se cuenta con denominaciones, no con un número suelto.
    r = api.post(f"/caja/turnos/{turno['id']}/cerrar", headers=h, json={"contados": {efectivo: 57000, digital: 26000}})
    assert r.status_code == 400 and "billetes y monedas" in r.json()["detail"]
    conteo = {denominacion(h, 50000): 1, denominacion(h, 5000): 1, denominacion(h, 1000): 2, denominacion(h, 100): 0}
    contados = {c["caja_id"]: 0 for c in turno["cajas"] if not c["usa_denominaciones"]} | {digital: 25000}
    r = api.post(f"/caja/turnos/{turno['id']}/cerrar", headers=h,
                 json={"contados": contados, "conteo": conteo, "notas": "Faltó un recibo de Nequi"})
    assert r.status_code == 200, r.text
    cerrado = r.json()
    ef, dig = _caja(cerrado, "Efectivo"), _caja(cerrado, "Digital")
    assert (ef["contado"], ef["diferencia"], dig["diferencia"]) == (57000, 0, -1000)
    assert [(d["valor"], d["cantidad"]) for d in cerrado["conteo"]] == [(50000, 1), (5000, 1), (1000, 2)]
    assert cerrado["cerrada_por"] and cerrado["notas"] == "Faltó un recibo de Nequi"
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s ORDER BY id DESC LIMIT 1",
                         (turno["id"],)).fetchone()["detalle"]
    assert "Efectivo cuadra" in detalle and "Digital faltan $1.000" in detalle

    # Ya cerrado: ni se cierra otra vez ni recibe movimientos.
    r = api.post(f"/caja/turnos/{turno['id']}/cerrar", headers=h, json={"contados": contados})
    assert r.status_code == 400 and "ya está cerrado" in r.json()["detail"]
    r = mover(movimientos[0])
    assert r.status_code == 400 and "ya está cerrado" in r.json()["detail"]

    # Al abrir el siguiente se sugiere lo contado; la base distinta queda como diferencia de apertura.
    sin_turno = api.get("/caja/turno", headers=h).json()
    assert sin_turno["turno"] is None
    assert next(c for c in sin_turno["cajas"] if c["nombre"] == "Efectivo")["contado_anterior"] == 57000
    siguiente = _abrir(api, h, Efectivo=50000, Digital=25000)
    assert _caja(siguiente, "Efectivo")["diferencia_apertura"] == -7000
    assert _caja(siguiente, "Digital")["diferencia_apertura"] == 0
    # Una pantalla vieja que mueve plata en el turno ya cerrado no cae en el nuevo.
    assert mover(movimientos[0]).status_code == 400
    assert api.get("/caja/turno", headers=h).json()["turno"]["movimientos"] == []


def test_abrir_exige_la_base_de_cada_caja_activa(api, sesion):
    h = sesion("vendedor")
    _sin_turno(api, h)
    cajas = api.get("/caja/turno", headers=h).json()["cajas"]
    efectivo = next(c["id"] for c in cajas if c["nombre"] == "Efectivo")
    r = api.post("/caja/turnos", headers=h, json={"bases": {efectivo: 1000}})
    assert r.status_code == 400 and "Falta la base de" in r.json()["detail"] and "Digital" in r.json()["detail"]
    todas = {c["id"]: 0 for c in cajas}
    r = api.post("/caja/turnos", headers=h, json={"bases": todas | {str(uuid.uuid4()): 0}})
    assert r.status_code == 400 and "no existe o está desactivada" in r.json()["detail"]
    assert api.post("/caja/turnos", headers=h, json={"bases": todas | {efectivo: -1}}).status_code == 422


def test_cerrar_valida_el_conteo(api, sesion, denominacion):
    h = sesion("vendedor")
    turno = _abrir(api, h)
    efectivo = _caja(turno, "Efectivo")["caja_id"]
    otras = {c["caja_id"]: 0 for c in turno["cajas"] if not c["usa_denominaciones"]}
    digital = _caja(turno, "Digital")["caja_id"]
    cerrar = lambda body: api.post(f"/caja/turnos/{turno['id']}/cerrar", headers=h, json=body)

    r = cerrar({"contados": {k: v for k, v in otras.items() if k != digital}})
    assert (r.status_code, r.json()["detail"]) == (400, "Falta el conteo de la caja Digital.")
    r = cerrar({"contados": otras, "conteo": {str(uuid.uuid4()): 1}})
    assert r.status_code == 400 and "denominaciones indicadas no existe" in r.json()["detail"]
    r = cerrar({"contados": otras | {str(uuid.uuid4()): 0}})
    assert r.status_code == 400 and "no está en este turno" in r.json()["detail"]
    assert cerrar({"contados": otras, "conteo": {denominacion(h, 1000): -1}}).status_code == 422
    assert cerrar({"contados": otras, "conteo": {efectivo: 1}}).status_code == 400  # un id que no es denominación
    assert api.post(f"/caja/turnos/{uuid.uuid4()}/cerrar", headers=h, json={}).status_code == 404

    # Lo que falló no dejó nada a medias: el turno sigue abierto y se cierra bien.
    assert api.get("/caja/turno", headers=h).json()["turno"]["id"] == turno["id"]
    assert cerrar({"contados": otras}).status_code == 200


def test_movimiento_a_una_caja_fuera_del_turno(api, sesion):
    admin = sesion("admin")
    turno = _abrir(api, admin)
    caja = api.post("/config/cajas", headers=admin, json={"nombre": f"Caja fuerte {uuid.uuid4().hex[:4]}"}).json()
    r = api.post(f"/caja/turnos/{turno['id']}/movimientos", headers=admin, json={
        "tipo": "ingreso", "caja_destino_id": caja["id"], "monto": 1000, "motivo": "Prueba"})
    assert r.status_code == 400 and "no está registrada en el turno" in r.json()["detail"]
    _sin_turno(api, admin)
    api.patch(f"/config/cajas/{caja['id']}", headers=admin, json={"activo": False})


def test_historial_exige_permiso(api, sesion):
    vendedor, admin = sesion("vendedor"), sesion("admin")
    turno = _abrir(api, vendedor, Efectivo=1000)
    _sin_turno(api, vendedor)
    assert api.get("/caja/turnos", headers=vendedor).status_code == 403
    assert api.get(f"/caja/turnos/{turno['id']}", headers=vendedor).status_code == 403

    lista = api.get("/caja/turnos", headers=admin).json()
    fila = next(t for t in lista if t["id"] == turno["id"])
    assert fila["cerrada_en"] and fila["ventas"] == 0
    assert next(c for c in fila["cajas"] if c["caja"] == "Efectivo")["diferencia"] == -1000
    assert [t["numero"] for t in lista] == sorted((t["numero"] for t in lista), reverse=True)
    assert api.get("/caja/turnos", headers=admin, params={"desde": "2000-01-01", "hasta": "2000-01-31"}).json() == []

    detalle = api.get(f"/caja/turnos/{turno['id']}", headers=admin).json()
    assert detalle["numero"] == turno["numero"] and detalle["cerrada_por"]
    assert api.get(f"/caja/turnos/{uuid.uuid4()}", headers=admin).status_code == 404
