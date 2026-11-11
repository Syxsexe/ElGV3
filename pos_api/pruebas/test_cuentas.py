"""Cuentas por mesa o alias: consumos, cobro (pasa a una venta) y cancelación."""
import uuid

import pytest


@pytest.fixture
def articulo(bd, f):
    def _crear(precio=5000):
        with bd.transaction():
            return str(f.producto(precio=precio))
    return _crear


@pytest.fixture
def mesa(bd):
    """Una mesa nueva, activa y sin cuenta."""
    def _crear():
        return str(bd.execute("INSERT INTO mesas (nombre) VALUES (%s) RETURNING id",
                              (f"M{uuid.uuid4().hex[:5]}",)).fetchone()["id"])
    return _crear


def _ultima_auditoria(bd, cuenta_id):
    return bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s ORDER BY id DESC LIMIT 1",
                      (cuenta_id,)).fetchone()["detalle"]


def test_cuenta_completa(api, sesion, bd, f, turno, articulo, mesa):
    h = sesion("vendedor")
    m = mesa()
    cerveza, papas = articulo(6000), articulo(4000)

    r = api.post("/cuentas", headers=h, json={"mesa_id": m, "alias": "  Los del fondo "})
    assert r.status_code == 201, r.text
    cuenta = r.json()
    assert (cuenta["alias"], cuenta["estado"], cuenta["items"]) == ("Los del fondo", "abierta", [])
    otra = api.post("/cuentas", headers=h, json={"mesa_id": m, "alias": "Otro"})
    assert (otra.status_code, otra.json()["detail"]) == (400, "Esa mesa ya tiene una cuenta abierta.")

    agregar = lambda art, cant=1: api.post(f"/cuentas/{cuenta['id']}/items", headers=h,
                                           json={"articulo_id": art, "cantidad": cant})
    assert agregar(cerveza).status_code == 201
    assert agregar(papas, 2).status_code == 201
    cuenta = agregar(cerveza).json()  # mismo artículo y precio: suma a la línea
    assert [(i["cantidad"], i["precio_unit"]) for i in cuenta["items"]] == [(2, 6000), (2, 4000)]
    # Cambia el precio: lo nuevo va en otra línea, lo ya pedido conserva su precio.
    bd.execute("UPDATE articulos SET precio_venta = 7000 WHERE id = %s", (cerveza,))
    cuenta = agregar(cerveza).json()
    assert [(i["cantidad"], i["precio_unit"]) for i in cuenta["items"]] == [(2, 6000), (2, 4000), (1, 7000)]
    assert (cuenta["total"], cuenta["lineas"]) == (27000, 3)

    papas_id = cuenta["items"][1]["id"]
    r = api.patch(f"/cuentas/{cuenta['id']}/items/{papas_id}", headers=h, json={"cantidad": 1})
    assert r.json()["total"] == 23000
    assert "Bajó" in _ultima_auditoria(bd, cuenta["id"]) and "de 2 a 1" in _ultima_auditoria(bd, cuenta["id"])
    assert api.patch(f"/cuentas/{cuenta['id']}/items/{papas_id}", headers=h, json={"cantidad": 0}).status_code == 422
    assert api.patch(f"/cuentas/{cuenta['id']}/items/{uuid.uuid4()}", headers=h, json={"cantidad": 1}).status_code == 404

    abiertas = api.get("/cuentas", headers=h).json()
    fila = next(c for c in abiertas if c["id"] == cuenta["id"])
    assert (fila["total"], fila["lineas"], fila["nombre"]) == (23000, 3, "Los del fondo")

    # Cobrar con el total viejo falla y dice el nuevo; con el correcto pasa a una venta.
    efectivo = str(f.metodo("efectivo"))
    cobrar = lambda **body: api.post(f"/cuentas/{cuenta['id']}/cobrar", headers=h,
                                     json={"sesion_id": str(turno), **body})
    r = cobrar(pagos=[{"metodo_pago_id": efectivo, "monto": 27000}])
    assert r.status_code == 400 and "el total es $23.000" in r.json()["detail"]
    r = cobrar(descuento=3000, pagos=[{"metodo_pago_id": efectivo, "monto": 20000}])
    assert r.status_code == 201, r.text
    venta = r.json()
    assert (venta["total"], venta["cuenta_numero"], len(venta["lineas"])) == (20000, cuenta["numero"], 3)
    assert [l["precio_unit"] for l in venta["lineas"]] == [6000, 4000, 7000]
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s", (venta["id"],)).fetchone()["detalle"]
    assert f"de la cuenta #{cuenta['numero']} (mesa" in detalle and "Los del fondo)" in detalle

    cobrada = api.get(f"/cuentas/{cuenta['id']}", headers=h).json()
    assert (cobrada["estado"], cobrada["items"], cobrada["venta_numero"]) == ("cobrada", [], venta["numero"])
    assert all(c["id"] != cuenta["id"] for c in api.get("/cuentas", headers=h).json())
    r = agregar(cerveza)
    assert (r.status_code, r.json()["detail"]) == (400, f"La cuenta #{cuenta['numero']} ya se cobró (venta #{venta['numero']}).")
    assert cobrar(pagos=[{"metodo_pago_id": efectivo, "monto": 1}]).status_code == 400
    # La mesa quedó libre.
    assert api.post("/cuentas", headers=h, json={"mesa_id": m, "alias": "Siguientes"}).status_code == 201


def test_abrir_y_editar_cuenta(api, sesion, bd, f, mesa):
    h = sesion("vendedor")
    r = api.post("/cuentas", headers=h, json={"mesa_id": mesa()})
    assert (r.status_code, r.json()["detail"]) == (400, "Escribe un nombre para la cuenta o elige un cliente.")
    r = api.post("/cuentas", headers=h, json={"alias": "x", "mesa_id": str(uuid.uuid4())})
    assert (r.status_code, r.json()["detail"]) == (404, "La mesa no existe.")
    r = api.post("/cuentas", headers=h, json={"cliente_id": str(uuid.uuid4())})
    assert (r.status_code, r.json()["detail"]) == (404, "El cliente no existe.")
    inactiva = mesa()
    bd.execute("UPDATE mesas SET activa = false WHERE id = %s", (inactiva,))
    r = api.post("/cuentas", headers=h, json={"alias": "x", "mesa_id": inactiva})
    assert r.status_code == 400 and "desactivada" in r.json()["detail"]

    # Sin mesa, a nombre de un cliente (si llega alias también, gana el cliente).
    cliente = f.cliente()
    cuenta = api.post("/cuentas", headers=h, json={"cliente_id": str(cliente), "alias": "ignorado"}).json()
    assert (cuenta["cliente_id"], cuenta["alias"], cuenta["mesa"]) == (str(cliente), None, None)

    # Pasar a una mesa y a un alias; quitarle la mesa.
    m = mesa()
    r = api.patch(f"/cuentas/{cuenta['id']}", headers=h, json={"mesa_id": m, "alias": "Juan"})
    assert r.status_code == 200, r.text
    assert (r.json()["mesa_id"], r.json()["alias"], r.json()["cliente_id"]) == (m, "Juan", None)
    assert "ahora mesa" in _ultima_auditoria(bd, cuenta["id"])
    r = api.patch(f"/cuentas/{cuenta['id']}", headers=h, json={"mesa_id": None, "cliente_id": None})
    assert (r.json()["mesa_id"], r.json()["alias"]) == (None, "Juan")  # cliente null no borra el nombre
    assert api.patch(f"/cuentas/{uuid.uuid4()}", headers=h, json={"alias": "x"}).status_code == 404

    # Si su mesa se desactiva, la cuenta igual se renombra (la mesa no cambia).
    m2 = mesa()
    api.patch(f"/cuentas/{cuenta['id']}", headers=h, json={"mesa_id": m2})
    bd.execute("UPDATE mesas SET activa = false WHERE id = %s", (m2,))
    r = api.patch(f"/cuentas/{cuenta['id']}", headers=h, json={"mesa_id": m2, "alias": "Juan Pablo"})
    assert (r.status_code, r.json()["alias"], r.json()["mesa_id"]) == (200, "Juan Pablo", m2)
    r = api.patch(f"/cuentas/{cuenta['id']}", headers=h, json={"mesa_id": inactiva})
    assert r.status_code == 400 and "desactivada" in r.json()["detail"]


def test_cancelar_cuenta(api, sesion, bd, articulo):
    h = sesion("vendedor")
    vacia = api.post("/cuentas", headers=h, json={"alias": "Por error"}).json()
    r = api.post(f"/cuentas/{vacia['id']}/cancelar", headers=h, json={})
    assert (r.status_code, r.json()["estado"]) == (200, "cancelada")

    cuenta = api.post("/cuentas", headers=h, json={"alias": "Se fueron"}).json()
    item = api.post(f"/cuentas/{cuenta['id']}/items", headers=h,
                    json={"articulo_id": articulo(8000), "cantidad": 2}).json()["items"][0]
    r = api.post(f"/cuentas/{cuenta['id']}/cancelar", headers=h, json={"motivo": "  "})
    assert (r.status_code, r.json()["detail"]) == (400, "La cuenta tiene consumos por $16.000: escribe por qué se cancela.")
    r = api.post(f"/cuentas/{cuenta['id']}/cancelar", headers=h, json={"motivo": "Se fueron sin pagar"})
    assert r.status_code == 200, r.text
    cancelada = r.json()
    # Conserva lo cancelado, con el motivo en las notas y en la auditoría.
    assert (cancelada["estado"], len(cancelada["items"]), cancelada["total"]) == ("cancelada", 1, 16000)
    assert cancelada["notas"] == "Cancelada: Se fueron sin pagar"
    assert _ultima_auditoria(bd, cuenta["id"]).endswith("con consumos por $16.000: Se fueron sin pagar")

    r = api.delete(f"/cuentas/{cuenta['id']}/items/{item['id']}", headers=h)
    assert (r.status_code, r.json()["detail"]) == (400, f"La cuenta #{cuenta['numero']} ya se canceló.")
    assert api.post(f"/cuentas/{cuenta['id']}/cancelar", headers=h, json={"motivo": "x"}).status_code == 400
    assert api.post(f"/cuentas/{uuid.uuid4()}/cancelar", headers=h, json={}).status_code == 404


def test_quitar_consumo_y_cobrar_vacia(api, sesion, bd, turno, articulo):
    h = sesion("vendedor")
    cuenta = api.post("/cuentas", headers=h, json={"alias": "Ana"}).json()
    art = articulo(2500)
    item = api.post(f"/cuentas/{cuenta['id']}/items", headers=h, json={"articulo_id": art}).json()["items"][0]
    assert item["cantidad"] == 1
    r = api.delete(f"/cuentas/{cuenta['id']}/items/{item['id']}", headers=h)
    assert (r.status_code, r.json()["items"]) == (200, [])
    assert "Quitó 1 ×" in _ultima_auditoria(bd, cuenta["id"]) and "($2.500)" in _ultima_auditoria(bd, cuenta["id"])
    assert api.delete(f"/cuentas/{cuenta['id']}/items/{item['id']}", headers=h).status_code == 404

    r = api.post(f"/cuentas/{cuenta['id']}/cobrar", headers=h, json={"sesion_id": str(turno)})
    assert r.status_code == 400 and "no tiene consumos" in r.json()["detail"]
    bd.execute("UPDATE articulos SET activo = false WHERE id = %s", (art,))
    r = api.post(f"/cuentas/{cuenta['id']}/items", headers=h, json={"articulo_id": art})
    assert r.status_code == 400 and "ya no se vende" in r.json()["detail"]
    r = api.post(f"/cuentas/{cuenta['id']}/items", headers=h, json={"articulo_id": str(uuid.uuid4())})
    assert r.status_code == 404
    assert api.get("/cuentas").status_code == 401


def test_cobrar_con_fiado_al_cliente_de_la_cuenta(api, sesion, bd, f, turno, articulo):
    h = sesion("vendedor")
    cliente = f.cliente(limite=100000)
    cuenta = api.post("/cuentas", headers=h, json={"cliente_id": str(cliente)}).json()
    art = articulo(9000)
    api.post(f"/cuentas/{cuenta['id']}/items", headers=h, json={"articulo_id": art})
    # Un artículo que se desactiva después de pedirlo igual se cobra.
    bd.execute("UPDATE articulos SET activo = false WHERE id = %s", (art,))
    r = api.post(f"/cuentas/{cuenta['id']}/cobrar", headers=h, json={"sesion_id": str(turno), "fiado": 9000})
    assert r.status_code == 201, r.text
    assert (r.json()["cliente_id"], r.json()["fiado"], r.json()["metodo"]) == (str(cliente), 9000, "credito")


def test_no_se_agrega_mas_de_lo_que_hay_en_stock(api, sesion, bd, f, turno):
    h = sesion("vendedor")
    with bd.transaction():
        cerveza = f.producto(precio=6000, stock=2)
        plato = f.producto(precio=12000, tipo_categoria="cocina", impuesto="INC8", stock=0)
    cuenta = api.post("/cuentas", headers=h, json={"alias": "Stock"}).json()
    agregar = lambda art, cant=1: api.post(f"/cuentas/{cuenta['id']}/items", headers=h,
                                           json={"articulo_id": str(art), "cantidad": cant})
    assert agregar(cerveza, 2).status_code == 201
    r = agregar(cerveza)
    assert (r.status_code, r.json()["detail"]) == (400, f"No hay stock suficiente de {_nombre(bd, cerveza)} (hay 2, la cuenta lleva 3)")
    assert agregar(plato, 5).status_code == 201  # la cocina no lleva stock
    item = api.get(f"/cuentas/{cuenta['id']}", headers=h).json()["items"][0]
    assert api.patch(f"/cuentas/{cuenta['id']}/items/{item['id']}", headers=h, json={"cantidad": 3}).status_code == 400
    assert api.patch(f"/cuentas/{cuenta['id']}/items/{item['id']}", headers=h, json={"cantidad": 1}).status_code == 200

    # Si otra venta se lleva el stock, el cobro falla con el faltante.
    bd.execute("UPDATE productos SET stock = 0 WHERE articulo_id = %s", (cerveza,))
    efectivo = str(f.metodo("efectivo"))
    total = api.get(f"/cuentas/{cuenta['id']}", headers=h).json()["total"]
    r = api.post(f"/cuentas/{cuenta['id']}/cobrar", headers=h,
                 json={"sesion_id": str(turno), "pagos": [{"metodo_pago_id": efectivo, "monto": total}]})
    assert (r.status_code, r.json()["detail"]) == (400, f"No hay stock suficiente de {_nombre(bd, cerveza)} (hay 0, se necesitan 1)")


def _nombre(bd, articulo):
    return bd.execute("SELECT nombre FROM articulos WHERE id = %s", (articulo,)).fetchone()["nombre"]
