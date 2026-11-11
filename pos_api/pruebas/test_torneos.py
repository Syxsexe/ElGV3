"""Torneos: inscripciones (pago, fiado, gratis), premios con stock e historial."""
import datetime
import uuid

import pytest


@pytest.fixture
def juego(f):
    return lambda nombre="MTG": str(f.id_de("juegos", "nombre", nombre))


@pytest.fixture
def premio(bd, f):
    def _crear(costo=11050, stock=10):
        with bd.transaction():
            pid = f.producto(precio=20000, costo=costo)
            bd.execute("UPDATE productos SET stock = %s WHERE articulo_id = %s", (stock, pid))
        return str(pid)
    return _crear


def _esperado(bd, turno, caja):
    return bd.execute(
        """SELECT esperado FROM v_sesion_cajas vs JOIN cajas c ON c.id = vs.caja_id
            WHERE vs.sesion_id = %s AND c.nombre = %s""", (turno, caja)).fetchone()["esperado"]


def test_torneo_completo(api, sesion, bd, f, turno, juego, premio):
    h = sesion("vendedor")
    carlos, sebastian = f.cliente(), f.cliente(limite=50000)
    bd.execute("UPDATE clientes SET dias_credito = 7 WHERE tercero_id = %s", (sebastian,))
    sobre = premio(costo=11050, stock=10)
    antes = {c: _esperado(bd, turno, c) for c in ("Efectivo", "Digital")}
    assert api.get("/torneos/inscripcion", headers=h).json()["precio"] == 15000

    r = api.post("/torneos", headers=h, json={
        "nombre": "Yugi semanal", "juego_id": juego("Yu-Gi-Oh!"), "sesion_id": str(turno), "notas": "Formato avanzado",
        "participantes": [
            {"cliente_id": str(carlos), "forma": "pago", "metodo_pago_id": str(f.metodo("efectivo"))},
            {"cliente_id": str(sebastian), "forma": "fiado"},
            {"alias": "Byron", "forma": "pago", "metodo_pago_id": str(f.metodo("nequi"))},
            {"alias": "Ana", "forma": "gratis"},
        ],
        "premios": [{"producto_id": sobre, "cantidad": 2}]})
    assert r.status_code == 201, r.text
    t = r.json()
    assert (t["recaudado"], t["costo_premios"], t["ganancia"], t["jugadores"], t["jugadores_gratis"]) == \
        (45000, 22100, 22900, 4, 1)
    assert [(p["forma"], p["monto"]) for p in t["participantes"]] == \
        [("Efectivo", 15000), ("Crédito", 15000), ("Nequi", 15000), ("Gratis", 0)]
    assert [p["nombre"] for p in t["participantes"]][2:] == ["Byron", "Ana"]
    assert [(p["cantidad"], p["costo_unit"]) for p in t["premios"]] == [(2, 11050)]

    venta = bd.execute("SELECT total, pagado, fiado FROM v_ventas WHERE id = %s", (t["venta_id"],)).fetchone()
    assert venta == {"total": 45000, "pagado": 30000, "fiado": 15000}
    cargo = bd.execute("SELECT cliente_id, vence_en FROM cargos_credito WHERE venta_id = %s", (t["venta_id"],)).fetchone()
    hoy = bd.execute("SELECT current_date AS hoy").fetchone()["hoy"]
    assert cargo == {"cliente_id": sebastian, "vence_en": hoy + datetime.timedelta(days=7)}
    assert bd.execute("SELECT stock FROM productos WHERE articulo_id = %s", (sobre,)).fetchone()["stock"] == 8
    assert _esperado(bd, turno, "Efectivo") - antes["Efectivo"] == 15000
    assert _esperado(bd, turno, "Digital") - antes["Digital"] == 15000
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s", (t["id"],)).fetchone()["detalle"]
    assert detalle.startswith("Registró el torneo «Yugi semanal» (Yu-Gi-Oh!): 4 jugador(es), 1 gratis; recaudó $45.000")
    assert "(Efectivo $15.000, crédito $15.000, Nequi $15.000); premios por $22.100" in detalle

    assert any(x["id"] == t["id"] for x in api.get("/torneos", headers=h, params={"juego_id": juego("Yu-Gi-Oh!")}).json())
    assert all(x["id"] != t["id"] for x in api.get("/torneos", headers=h, params={"juego_id": juego("MTG")}).json())
    assert api.get(f"/torneos/{t['id']}", headers=h).json()["notas"] == "Formato avanzado"
    assert api.get(f"/torneos/{uuid.uuid4()}", headers=h).status_code == 404


def test_todos_gratis_y_precio_propio(api, sesion, f, turno, juego):
    h = sesion("vendedor")
    r = api.post("/torneos", headers=h, json={
        "nombre": "Casual", "juego_id": juego(), "participantes": [{"alias": "A", "forma": "gratis"}, {"alias": "B", "forma": "gratis"}]})
    assert r.status_code == 201, r.text  # sin cobro no hace falta turno
    assert (r.json()["venta_id"], r.json()["recaudado"], r.json()["jugadores_gratis"]) == (None, 0, 2)

    r = api.post("/torneos", headers=h, json={
        "nombre": "Liga", "juego_id": juego(), "sesion_id": str(turno), "precio": 10000,
        "participantes": [{"alias": "A", "forma": "pago", "metodo_pago_id": str(f.metodo("efectivo"))}]})
    assert r.status_code == 201 and r.json()["recaudado"] == 10000


def test_torneo_rechazado(api, sesion, bd, f, turno, juego, premio):
    h = sesion("vendedor")
    efectivo = str(f.metodo("efectivo"))
    cliente = f.cliente()
    pago = {"alias": "X", "forma": "pago", "metodo_pago_id": efectivo}
    registrar = lambda participantes, **extra: api.post("/torneos", headers=h, json={
        "nombre": "T", "juego_id": juego(), "sesion_id": str(turno), "participantes": participantes, **extra})

    assert registrar([]).status_code == 422
    r = registrar([{"cliente_id": str(cliente), "forma": "gratis"}] * 2)
    assert (r.status_code, r.json()["detail"]) == (400, "Un cliente está inscrito dos veces.")
    r = registrar([{"alias": "Byron", "forma": "fiado"}])
    assert (r.status_code, r.json()["detail"]) == (400, "Byron no es cliente registrado: no se le puede dar crédito.")
    r = registrar([{"alias": "Y", "forma": "pago"}])
    assert (r.status_code, r.json()["detail"]) == (400, "A cada jugador que paga indícale el método.")
    r = registrar([{"alias": "Y", "cliente_id": str(cliente), "forma": "gratis"}])
    assert r.status_code == 400 and "uno de los dos" in r.json()["detail"]
    r = registrar([pago], sesion_id=None)
    assert (r.status_code, r.json()["detail"]) == (400, "Para cobrar inscripciones indica el turno de caja.")
    r = registrar([pago], precio=0)
    assert r.status_code == 400 and "márcalos así" in r.json()["detail"]
    r = registrar([{"cliente_id": str(uuid.uuid4()), "forma": "gratis"}])
    assert (r.status_code, r.json()["detail"]) == (404, "Uno de los clientes no existe.")
    r = registrar([pago], juego_id=str(uuid.uuid4()))
    assert (r.status_code, r.json()["detail"]) == (404, "El juego no existe.")

    sin_cupo = f.cliente(limite=0)
    r = registrar([pago, {"cliente_id": str(sin_cupo), "forma": "fiado"}])
    assert r.status_code == 400 and "no tiene cupo de crédito" in r.json()["detail"]
    r = registrar([pago], premios=[{"producto_id": str(uuid.uuid4()), "cantidad": 1}])
    assert (r.status_code, r.json()["detail"]) == (400, "Los premios son productos de tienda activos (los que tienen stock).")
    with bd.transaction():
        de_cocina = f.producto(tipo_categoria="cocina")
    assert registrar([pago], premios=[{"producto_id": str(de_cocina), "cantidad": 1}]).status_code == 400
    inactivo = f.cliente()
    bd.execute("UPDATE clientes SET activo = false WHERE tercero_id = %s", (inactivo,))
    r = registrar([{"cliente_id": str(inactivo), "forma": "gratis"}])
    assert r.status_code == 400 and r.json()["detail"].startswith("Están desactivados como clientes:")
    sobre = premio()
    r = registrar([pago], premios=[{"producto_id": sobre, "cantidad": 1}, {"producto_id": sobre, "cantidad": 1}])
    assert r.status_code == 400 and "dos veces" in r.json()["detail"]
    # Nada de lo rechazado quedó a medias.
    assert bd.execute("SELECT stock FROM productos WHERE articulo_id = %s", (sobre,)).fetchone()["stock"] == 10
    assert bd.execute("SELECT count(*) AS n FROM torneos WHERE nombre = 'T'").fetchone()["n"] == 0
    assert api.post("/torneos", json={}).status_code == 401


def test_varios_fiados_en_un_torneo(api, sesion, bd, f, turno, juego):
    h = sesion("vendedor")
    clientes = [f.cliente(limite=20000) for _ in range(3)]
    r = api.post("/torneos", headers=h, json={
        "nombre": "Fiados", "juego_id": juego(), "sesion_id": str(turno),
        "participantes": [{"cliente_id": str(c), "forma": "fiado"} for c in clientes]})
    assert r.status_code == 201, r.text
    t = r.json()
    assert [p["forma"] for p in t["participantes"]] == ["Crédito"] * 3
    cargos = bd.execute("SELECT cliente_id FROM cargos_credito WHERE venta_id = %s", (t["venta_id"],)).fetchall()
    assert sorted(c["cliente_id"] for c in cargos) == sorted(clientes)
    # Cada jugador apunta a SU cargo.
    ligados = bd.execute(
        """SELECT tp.cliente_id = c.cliente_id AS propio FROM torneo_participantes tp
             JOIN cargos_credito c ON c.id = tp.cargo_id WHERE tp.torneo_id = %s""", (t["id"],)).fetchall()
    assert [x["propio"] for x in ligados] == [True] * 3


def test_premios_con_costo_y_precio(api, sesion, bd, premio):
    pid = premio(costo=4000, stock=3)
    nombre = bd.execute("SELECT nombre FROM articulos WHERE id = %s", (pid,)).fetchone()["nombre"]
    r = api.get("/torneos/premios", headers=sesion("vendedor"), params={"q": nombre})
    assert r.status_code == 200
    assert [(p["id"], p["costo"], p["precio_venta"], p["stock"]) for p in r.json()] == [(pid, 4000, 20000, 3)]
    assert api.get("/torneos/premios", headers=sesion("vendedor"), params={"q": "x"}).status_code == 422
