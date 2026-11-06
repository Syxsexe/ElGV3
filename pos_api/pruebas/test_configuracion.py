"""Datos del negocio, cajas, métodos de pago y catálogos simples."""
import uuid


def test_leer_es_para_todos_y_editar_exige_permiso(api, sesion):
    vendedor = sesion("vendedor")
    assert api.get("/config/cajas", headers=vendedor).status_code == 200
    assert api.get("/config/mesas", headers=vendedor).status_code == 200
    assert api.post("/config/mesas", headers=vendedor, json={"nombre": "Terraza"}).status_code == 403
    assert api.patch("/config/empresa", headers=vendedor, json={"nombre": "X"}).status_code == 403


def test_empresa(api, sesion, f, bd):
    h = sesion("admin")
    if bd.execute("SELECT count(*) AS n FROM empresa").fetchone()["n"] == 0:
        bd.execute("INSERT INTO empresa (tercero_id) VALUES (%s)", (f.tercero("El G", documento="900123456"),))
    pasto = api.get("/config/municipios", headers=h, params={"q": "pasto"}).json()
    assert pasto[0]["nombre"] == "PASTO" and pasto[0]["departamento"] == "NARIÑO"
    assert api.get("/config/municipios", headers=h, params={"q": "bogota"}).json()  # sin tilde

    r = api.patch("/config/empresa", headers=h, json={
        "tipo_identificacion": "31", "numero_identificacion": "800197268", "nombre": "El G SAS",
        "municipio_id": pasto[0]["id"], "direccion": "  ", "regimen_tributario": "simple"})
    assert r.status_code == 200, r.text
    e = r.json()
    assert (e["nombre"], e["dv"], e["municipio"], e["direccion"], e["regimen_tributario"]) == (
        "El G SAS", 4, "PASTO", None, "simple")
    # Reenviar lo mismo no audita nada; cambiar un campo audita solo ese.
    tercero_id = bd.execute("SELECT tercero_id FROM empresa").fetchone()["tercero_id"]
    n = lambda: bd.execute("SELECT count(*) AS n FROM auditoria WHERE entidad_id = %s", (tercero_id,)).fetchone()["n"]
    antes = n()
    api.patch("/config/empresa", headers=h, json={"nombre": "El G SAS", "regimen_tributario": "simple"})
    assert n() == antes
    api.patch("/config/empresa", headers=h, json={"nombre": "El G S.A.S.", "regimen_tributario": "simple"})
    assert bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s ORDER BY id DESC LIMIT 1",
                      (tercero_id,)).fetchone()["detalle"] == "Editó los datos del negocio: nombre=El G S.A.S."
    assert api.patch("/config/empresa", headers=h, json={"tipo_identificacion": "99"}).status_code == 400
    assert api.patch("/config/empresa", headers=h, json={"regimen_tributario": "otro"}).status_code == 422


def test_cajas_y_metodos(api, sesion):
    h = sesion("admin")
    nombre = f"Caja menor {uuid.uuid4().hex[:4]}"
    caja = api.post("/config/cajas", headers=h, json={"nombre": nombre}).json()
    otra_con_billetes = api.post("/config/cajas", headers=h, json={"nombre": nombre + " b", "usa_denominaciones": True})
    assert (otra_con_billetes.status_code, otra_con_billetes.json()["detail"]) == (
        400, "Solo una caja puede contarse en billetes y monedas.")

    metodo = api.post("/config/metodos-pago", headers=h, json={"nombre": f"Bono Regalo {nombre[-4:]}", "caja_id": caja["id"]})
    assert metodo.status_code == 201 and metodo.json()["codigo"] == f"bono_regalo_{nombre[-4:]}"
    assert any(m["nombre"].startswith("Bono Regalo") for m in api.get("/config/metodos-pago", headers=h).json())

    # Una caja con métodos activos no se desactiva; sin ellos sí, y entonces sus métodos no se activan.
    r = api.patch(f"/config/cajas/{caja['id']}", headers=h, json={"activo": False})
    assert r.status_code == 400 and "métodos de pago activos" in r.json()["detail"]
    api.patch(f"/config/metodos-pago/{metodo.json()['id']}", headers=h, json={"activo": False})
    assert api.patch(f"/config/cajas/{caja['id']}", headers=h, json={"activo": False}).json()["activo"] is False
    r = api.patch(f"/config/metodos-pago/{metodo.json()['id']}", headers=h, json={"activo": True})
    assert r.status_code == 400 and "desactivada" in r.json()["detail"]
    caja_activa = next(c for c in api.get("/config/cajas", headers=h).json() if c["nombre"] == "Efectivo")
    assert {"efectivo"} <= {m["codigo"] for m in caja_activa["metodos"]}


def test_metodo_con_pagos_no_cambia_de_caja(api, sesion, f, bd, turno):
    h = sesion("admin")
    caja = api.post("/config/cajas", headers=h, json={"nombre": f"Datáfono {uuid.uuid4().hex[:4]}"}).json()
    metodo = api.post("/config/metodos-pago", headers=h, json={"nombre": f"QR {caja['nombre'][-4:]}", "caja_id": caja["id"]}).json()
    digital = f.caja("Digital")
    with bd.transaction():
        s, prod = turno, f.producto(precio=1000)
        bd.execute("INSERT INTO sesion_cajas (sesion_id, caja_id, base) VALUES (%s, %s, 0)", (s, caja["id"]))
        v = f.venta(s, [(prod, 1, 1000)])
        bd.execute("INSERT INTO pagos_venta (venta_id, metodo_pago_id, monto) VALUES (%s, %s, 1000)", (v, metodo["id"]))
    r = api.patch(f"/config/metodos-pago/{metodo['id']}", headers=h, json={"caja_id": str(digital)})
    assert r.status_code == 400 and "no puede cambiar de caja" in r.json()["detail"]


def test_catalogos_simples(api, sesion):
    h = sesion("admin")
    mesas = api.get("/config/mesas", headers=h).json()
    nombres = [m["nombre"] for m in mesas]
    assert nombres.index("2") < nombres.index("10")  # orden numérico
    nueva = api.post("/config/mesas", headers=h, json={"nombre": f"Terraza {uuid.uuid4().hex[:4]}"}).json()
    assert api.post("/config/mesas", headers=h, json={"nombre": nueva["nombre"]}).json()["detail"] == "Ya existe una mesa con ese nombre."
    assert api.patch(f"/config/mesas/{nueva['id']}", headers=h, json={"activo": False}).json()["activo"] is False
    assert nueva["id"] not in [m["id"] for m in api.get("/config/mesas", headers=h).json()]
    assert nueva["id"] in [m["id"] for m in api.get("/config/mesas", headers=h, params={"todos": True}).json()]

    juego = api.post("/config/juegos", headers=h, json={"nombre": f"Pokémon {uuid.uuid4().hex[:4]}"}).json()
    assert api.patch(f"/config/juegos/{juego['id']}", headers=h, json={"nombre": juego["nombre"] + " TCG"}).json()["nombre"].endswith("TCG")
    assert api.get("/config/categorias-gasto", headers=h).status_code == 200
    assert api.get("/config/productos", headers=h).status_code == 422  # catálogo fuera de la lista


def test_bordes_de_configuracion(api, sesion, turno):
    h = sesion("admin")
    assert api.patch(f"/config/metodos-pago/{uuid.uuid4()}", headers=h, json={"activo": True}).status_code == 404
    largo = api.patch("/config/empresa", headers=h, json={"tipo_identificacion": "31", "numero_identificacion": "1234567890123456"})
    assert largo.status_code == 400 and "máximo 15" in largo.json()["detail"]

    # Una caja del turno abierto no cambia cómo se cuenta ni se desactiva.
    efectivo = next(c for c in api.get("/config/cajas", headers=h).json() if c["nombre"] == "Efectivo")
    r = api.patch(f"/config/cajas/{efectivo['id']}", headers=h, json={"usa_denominaciones": False})
    assert r.status_code == 400 and "turno abierto" in r.json()["detail"]


def test_reemplazar_un_metodo_con_el_mismo_nombre(api, sesion):
    h = sesion("admin")
    digital = next(c for c in api.get("/config/cajas", headers=h).json() if c["nombre"] == "Digital")
    nombre = f"Bancolombia {uuid.uuid4().hex[:4]}"
    viejo = api.post("/config/metodos-pago", headers=h, json={"nombre": nombre, "caja_id": digital["id"]}).json()
    api.patch(f"/config/metodos-pago/{viejo['id']}", headers=h, json={"nombre": nombre + " (viejo)", "activo": False})
    nuevo = api.post("/config/metodos-pago", headers=h, json={"nombre": nombre, "caja_id": digital["id"]})
    assert nuevo.status_code == 201 and nuevo.json()["codigo"] == viejo["codigo"] + "_2"
