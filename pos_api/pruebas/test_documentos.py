"""Documentos comerciales: crear, editar, convertir, vender y descartar."""
import uuid

import pytest


@pytest.fixture
def articulo(bd, f):
    def _crear(precio=10000):
        with bd.transaction():
            return str(f.producto(precio=precio))
    return _crear


def _auditoria(bd, entidad_id):
    return bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s ORDER BY id DESC LIMIT 1",
                      (entidad_id,)).fetchone()["detalle"]


def test_cadena_hasta_la_venta(api, sesion, bd, f, turno, articulo):
    h = sesion("vendedor")
    cliente = f.cliente(limite=100000)
    mesa, silla = articulo(200000), articulo(50000)
    r = api.post("/documentos", headers=h, json={
        "tipo": "cotizacion", "cliente_id": str(cliente), "vigente_hasta": "2099-12-31", "descuento": 20000,
        "items": [{"articulo_id": mesa, "cantidad": 1, "precio_unit": 180000},  # precio acordado
                  {"articulo_id": silla, "cantidad": 4},                       # precio de lista
                  {"descripcion": "Transporte", "cantidad": 1, "precio_unit": 15000}]})
    assert r.status_code == 201, r.text
    cot = r.json()
    assert (cot["estado"], cot["subtotal"], cot["total"]) == ("vigente", 395000, 375000)
    assert [(i["descripcion"], i["precio_unit"]) for i in cot["items"]][1:] == [(cot["items"][1]["articulo"], 50000), ("Transporte", 15000)]
    assert _auditoria(bd, cot["id"]).startswith(f"Creó la cotización #{cot['numero']} por $375.000 para")

    # Convertir: la cotización queda aceptada y no cambia.
    orden = api.post(f"/documentos/{cot['id']}/convertir", headers=h).json()
    assert (orden["tipo"], orden["origen_numero"], orden["total"], len(orden["items"])) == ("orden_pedido", cot["numero"], 375000, 3)
    cot = api.get(f"/documentos/{cot['id']}", headers=h).json()
    assert (cot["estado"], cot["hijo_numero"]) == ("aceptada", orden["numero"])
    r = api.put(f"/documentos/{cot['id']}", headers=h, json={"items": [{"articulo_id": mesa, "cantidad": 1}]})
    assert r.status_code == 400 and "ya se convirtió en la orden de pedido" in r.json()["detail"]
    assert api.post(f"/documentos/{cot['id']}/convertir", headers=h).status_code == 400

    remision = api.post(f"/documentos/{orden['id']}/convertir", headers=h).json()
    assert remision["tipo"] == "remision"
    r = api.post(f"/documentos/{remision['id']}/convertir", headers=h)
    assert r.status_code == 400 and "se vende" in r.json()["detail"]

    # Vender: la línea de texto libre lo impide hasta editarla.
    efectivo = str(f.metodo("efectivo"))
    vender = lambda **body: api.post(f"/documentos/{remision['id']}/vender", headers=h,
                                     json={"sesion_id": str(turno), **body})
    r = vender(pagos=[{"metodo_pago_id": efectivo, "monto": 375000}])
    assert r.status_code == 400 and "texto libre: Transporte" in r.json()["detail"]
    with bd.transaction():
        flete = bd.execute(
            """INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta)
               SELECT 'servicio', %s, c.id, i.id, 15000 FROM categorias c, impuestos i
                WHERE c.nombre = 'Torneos' AND i.codigo = 'IVA19' RETURNING id""", (f"Flete {uuid.uuid4().hex[:4]}",)).fetchone()["id"]
        bd.execute("INSERT INTO servicios (articulo_id) VALUES (%s)", (flete,))
    items = [{"articulo_id": i["articulo_id"], "cantidad": i["cantidad"], "precio_unit": i["precio_unit"]}
             for i in remision["items"][:2]] + [{"articulo_id": str(flete), "descripcion": "Transporte", "cantidad": 1}]
    r = api.put(f"/documentos/{remision['id']}", headers=h, json={
        "cliente_id": str(cliente), "descuento": 20000, "items": items})
    assert r.status_code == 200 and r.json()["total"] == 375000

    r = vender(pagos=[{"metodo_pago_id": efectivo, "monto": 300000}], fiado=75000)
    assert r.status_code == 201, r.text
    venta = r.json()
    assert (venta["total"], venta["descuento"], venta["fiado"], venta["cliente_id"]) == (375000, 20000, 75000, str(cliente))
    assert [l["precio_unit"] for l in venta["lineas"]] == [180000, 50000, 15000]
    assert venta["documento"]["estado"] == "facturada" and venta["documento"]["venta_numero"] == venta["numero"]
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s", (venta["id"],)).fetchone()["detalle"]
    assert f"de la remisión #{remision['numero']}" in detalle
    r = vender(pagos=[{"metodo_pago_id": efectivo, "monto": 375000}])
    assert r.status_code == 400 and "ya se vendió" in r.json()["detail"]
    r = api.post(f"/documentos/{remision['id']}/descartar", headers=h, json={"motivo": "anulado"})
    assert r.status_code == 400


def test_vencida_y_descartes(api, sesion, bd, articulo):
    h = sesion("vendedor")
    item = {"articulo_id": articulo(), "cantidad": 2}
    vieja = api.post("/documentos", headers=h, json={"tipo": "cotizacion", "vigente_hasta": "2020-01-01", "items": [item]}).json()
    assert vieja["estado"] == "vencida"
    r = api.post(f"/documentos/{vieja['id']}/convertir", headers=h)
    assert r.status_code == 400 and "venció" in r.json()["detail"]
    # Renovarla editando la vigencia.
    r = api.put(f"/documentos/{vieja['id']}", headers=h, json={"vigente_hasta": "2099-01-01", "items": [item]})
    assert r.json()["estado"] == "vigente"
    assert "Editó la cotización" in _auditoria(bd, vieja["id"])

    r = api.post(f"/documentos/{vieja['id']}/descartar", headers=h, json={"motivo": "rechazado", "explicacion": "Muy caro"})
    assert (r.status_code, r.json()["estado"], r.json()["notas"]) == (200, "rechazada", "Descartado: Muy caro")
    assert _auditoria(bd, vieja["id"]).endswith("como rechazado: Muy caro")
    r = api.post(f"/documentos/{vieja['id']}/descartar", headers=h, json={"motivo": "anulado"})
    assert r.status_code == 400 and "fue rechazada" in r.json()["detail"]
    assert api.post(f"/documentos/{vieja['id']}/descartar", headers=h, json={"motivo": "perdido"}).status_code == 422

    orden = api.post("/documentos", headers=h, json={"tipo": "orden_pedido", "items": [item]}).json()
    r = api.post(f"/documentos/{orden['id']}/descartar", headers=h, json={"motivo": "anulado"})
    assert r.json()["estado"] == "anulada"


def test_documento_rechazado(api, sesion, f, articulo):
    h = sesion("vendedor")
    item = {"articulo_id": articulo(1000), "cantidad": 1}
    crear = lambda **body: api.post("/documentos", headers=h, json={"tipo": "cotizacion", "items": [item], **body})
    r = crear(descuento=5000)
    assert (r.status_code, r.json()["detail"]) == (400, "El descuento ($5.000) supera el subtotal ($1.000).")
    r = crear(tipo="remision", vigente_hasta="2099-01-01")
    assert (r.status_code, r.json()["detail"]) == (400, "Solo una cotización lleva fecha de vigencia.")
    r = crear(items=[{"descripcion": "Algo", "cantidad": 1}])
    assert (r.status_code, r.json()["detail"]) == (400, "La línea «Algo» necesita su precio.")
    r = crear(items=[{"cantidad": 1, "precio_unit": 10}])
    assert r.status_code == 400 and "necesita su descripción" in r.json()["detail"]
    r = crear(items=[{"articulo_id": str(uuid.uuid4()), "cantidad": 1}])
    assert (r.status_code, r.json()["detail"]) == (404, "Uno de los artículos no existe.")
    r = crear(cliente_id=str(uuid.uuid4()))
    assert (r.status_code, r.json()["detail"]) == (404, "El cliente no existe.")
    assert crear(items=[]).status_code == 422
    assert crear(tipo="factura").status_code == 422
    assert api.get(f"/documentos/{uuid.uuid4()}", headers=h).status_code == 404
    assert api.get("/documentos").status_code == 401


def test_listar(api, sesion, f, articulo):
    h = sesion("vendedor")
    nombre = f"Cliente {uuid.uuid4().hex[:6]}"
    cliente = f.cliente(tercero_id=f.tercero(nombre=nombre))
    item = {"articulo_id": articulo(), "cantidad": 1}
    cot = api.post("/documentos", headers=h, json={"tipo": "cotizacion", "cliente_id": str(cliente), "items": [item]}).json()
    rem = api.post("/documentos", headers=h, json={"tipo": "remision", "items": [item]}).json()
    api.post(f"/documentos/{rem['id']}/descartar", headers=h, json={"motivo": "anulado"})

    assert [d["id"] for d in api.get("/documentos", headers=h, params={"q": nombre}).json()] == [cot["id"]]
    abiertos = [d["id"] for d in api.get("/documentos", headers=h, params={"estado": "abierto"}).json()]
    assert cot["id"] in abiertos and rem["id"] not in abiertos
    assert rem["id"] in [d["id"] for d in api.get("/documentos", headers=h, params={"tipo": "remision", "estado": "anulada"}).json()]
    por_numero = api.get("/documentos", headers=h, params={"q": f"#{cot['numero']}", "tipo": "cotizacion"}).json()
    assert [d["id"] for d in por_numero] == [cot["id"]]


def test_descartar_el_hijo_reabre_el_origen(api, sesion, articulo):
    h = sesion("vendedor")
    cot = api.post("/documentos", headers=h, json={"tipo": "cotizacion", "items": [{"articulo_id": articulo(), "cantidad": 1}]}).json()
    orden = api.post(f"/documentos/{cot['id']}/convertir", headers=h).json()
    assert api.get(f"/documentos/{cot['id']}", headers=h).json()["estado"] == "aceptada"
    api.post(f"/documentos/{orden['id']}/descartar", headers=h, json={"motivo": "anulado", "explicacion": "Cliente equivocado"})
    cot = api.get(f"/documentos/{cot['id']}", headers=h).json()
    assert cot["estado"] == "vigente"
    # Se puede convertir otra vez; el hijo que cuenta es el nuevo.
    otra = api.post(f"/documentos/{cot['id']}/convertir", headers=h).json()
    cot = api.get(f"/documentos/{cot['id']}", headers=h).json()
    assert (cot["estado"], cot["hijo_id"], cot["hijo_numero"]) == ("aceptada", otra["id"], otra["numero"])


def test_la_venta_respeta_el_impuesto_de_la_linea(api, sesion, bd, f, turno, articulo):
    h = sesion("vendedor")
    exento = str(f.impuesto("IVA0-EXENTO"))
    rem = api.post("/documentos", headers=h, json={"tipo": "remision", "items": [
        {"articulo_id": articulo(1000), "cantidad": 1, "impuesto_id": exento}]}).json()
    assert rem["items"][0]["impuesto"] == "IVA0-EXENTO"
    venta = api.post(f"/documentos/{rem['id']}/vender", headers=h, json={
        "sesion_id": str(turno), "pagos": [{"metodo_pago_id": str(f.metodo("efectivo")), "monto": 1000}]}).json()
    impuesto = bd.execute("""SELECT i.codigo FROM detalle_venta d JOIN impuestos i ON i.id = d.impuesto_id
                              WHERE d.venta_id = %s""", (venta["id"],)).fetchone()["codigo"]
    assert impuesto == "IVA0-EXENTO"


def test_validaciones_antes_de_escribir(api, sesion, bd, articulo):
    h = sesion("vendedor")
    item = {"articulo_id": articulo(1000), "cantidad": 1}
    primero = api.post("/documentos", headers=h, json={"tipo": "remision", "items": [item]}).json()
    assert api.post("/documentos", headers=h, json={"tipo": "remision", "descuento": 9999, "items": [item]}).status_code == 400
    segundo = api.post("/documentos", headers=h, json={"tipo": "remision", "items": [item]}).json()
    assert segundo["numero"] == primero["numero"] + 1  # el rechazado no gastó consecutivo

    inactivo = articulo()
    bd.execute("UPDATE articulos SET activo = false WHERE id = %s", (inactivo,))
    r = api.post("/documentos", headers=h, json={"tipo": "cotizacion", "items": [{"articulo_id": inactivo, "cantidad": 1}]})
    assert r.status_code == 400 and r.json()["detail"].startswith("Ya no se vende:")
    r = api.get("/documentos", headers=h, params={"q": "12345678901234567890"})
    assert (r.status_code, r.json()) == (200, [])
