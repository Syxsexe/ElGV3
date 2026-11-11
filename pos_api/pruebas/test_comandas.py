"""Comandas: lo pendiente de cocina de una cuenta, comentarios y reimpresión."""
import pytest


@pytest.fixture
def cuenta_con_cocina(api, sesion, bd, f, turno):
    """Una cuenta con 2 hamburguesas (cocina), 1 gaseosa (tienda) y 1 combo con algo de cocina."""
    h = sesion("vendedor")
    with bd.transaction():
        hamburguesa = f.producto(precio=15000, tipo_categoria="cocina", impuesto="INC8")
        gaseosa = f.producto(precio=3000)
        combo = bd.execute(
            "INSERT INTO articulos (tipo, nombre, categoria_id, impuesto_id, precio_venta) "
            "VALUES ('combo', 'Combo comanda', %s, %s, 16000) RETURNING id",
            (f.categoria("cocina"), f.impuesto("INC8"))).fetchone()["id"]
        bd.execute("INSERT INTO combos (articulo_id) VALUES (%s)", (combo,))
        bd.execute("INSERT INTO combo_productos VALUES (%s, %s, 1), (%s, %s, 1)", (combo, hamburguesa, combo, gaseosa))
    cuenta = api.post("/cuentas", headers=h, json={"alias": "Mesa comanda"}).json()
    for art, cant in [(hamburguesa, 2), (gaseosa, 1), (combo, 1)]:
        cuenta = api.post(f"/cuentas/{cuenta['id']}/items", headers=h, json={"articulo_id": str(art), "cantidad": cant}).json()
    return h, cuenta


def test_comanda_lleva_solo_lo_de_cocina_y_lo_nuevo(api, bd, cuenta_con_cocina):
    h, cuenta = cuenta_con_cocina
    por_nombre = {i["nombre"]: i for i in cuenta["items"]}
    assert [i["de_cocina"] for i in cuenta["items"]] == [True, False, True]
    hamburguesa, combo = cuenta["items"][0], cuenta["items"][2]

    r = api.post(f"/cuentas/{cuenta['id']}/comandas", headers=h, json={
        "items": [{"cuenta_item_id": hamburguesa["id"], "cantidad": 2, "comentario": " sin cebolla "},
                  {"cuenta_item_id": combo["id"], "cantidad": 1}],
        "notas": "Para llevar"})
    assert r.status_code == 201, r.text
    comanda = r.json()
    assert (comanda["nombre"], comanda["notas"], comanda["cuenta_numero"]) == ("Mesa comanda", "Para llevar", cuenta["numero"])
    assert comanda["usuario"]
    assert [(i["cantidad"], i["comentario"]) for i in comanda["items"]] == [(2, "sin cebolla"), (1, None)]
    assert comanda["items"][1]["componentes"].startswith("1 × Prod ")  # lo de cocina del combo

    # Ya enviado: no queda nada pendiente; una más de hamburguesa sí.
    cuenta = api.get(f"/cuentas/{cuenta['id']}", headers=h).json()
    assert [(i["enviado"]) for i in cuenta["items"]] == [2, 0, 1]
    r = api.post(f"/cuentas/{cuenta['id']}/comandas", headers=h,
                 json={"items": [{"cuenta_item_id": hamburguesa["id"], "cantidad": 1}]})
    assert (r.status_code, r.json()["detail"]) == (400, "Uno de los consumos ya no está pendiente para cocina: vuelve a abrir la comanda.")
    api.patch(f"/cuentas/{cuenta['id']}/items/{hamburguesa['id']}", headers=h, json={"cantidad": 3})
    r = api.post(f"/cuentas/{cuenta['id']}/comandas", headers=h,
                 json={"items": [{"cuenta_item_id": hamburguesa["id"], "cantidad": 2}]})
    assert (r.status_code, r.json()["detail"]) == (400, f"De {por_nombre[hamburguesa['nombre']]['nombre']} solo quedan 1 por mandar a cocina.")
    assert api.post(f"/cuentas/{cuenta['id']}/comandas", headers=h,
                    json={"items": [{"cuenta_item_id": hamburguesa["id"], "cantidad": 1}]}).status_code == 201

    # La gaseosa (tienda) no va a cocina.
    gaseosa = cuenta["items"][1]
    r = api.post(f"/cuentas/{cuenta['id']}/comandas", headers=h,
                 json={"items": [{"cuenta_item_id": gaseosa["id"], "cantidad": 1}]})
    assert r.status_code == 400

    # Historial para reimprimir, la más nueva primero; sigue tras cobrar.
    lista = api.get(f"/cuentas/{cuenta['id']}/comandas", headers=h).json()
    assert [len(c["items"]) for c in lista] == [1, 2] and lista[0]["numero"] > lista[1]["numero"]
    assert "Mandó a cocina la comanda" in bd.execute(
        "SELECT detalle FROM auditoria WHERE entidad_id = %s ORDER BY id DESC LIMIT 1", (cuenta["id"],)).fetchone()["detalle"]


def test_comanda_rechazada(api, sesion, cuenta_con_cocina):
    h, cuenta = cuenta_con_cocina
    item = cuenta["items"][0]["id"]
    assert api.post(f"/cuentas/{cuenta['id']}/comandas", headers=h, json={"items": []}).status_code == 422
    r = api.post(f"/cuentas/{cuenta['id']}/comandas", headers=h, json={"items": [
        {"cuenta_item_id": item, "cantidad": 1}, {"cuenta_item_id": item, "cantidad": 1}]})
    assert (r.status_code, r.json()["detail"]) == (400, "Un consumo aparece dos veces en la comanda.")
    api.post(f"/cuentas/{cuenta['id']}/cancelar", headers=h, json={"motivo": "prueba"})
    r = api.post(f"/cuentas/{cuenta['id']}/comandas", headers=h, json={"items": [{"cuenta_item_id": item, "cantidad": 1}]})
    assert r.status_code == 400 and "ya se canceló" in r.json()["detail"]
    assert api.get(f"/cuentas/{cuenta['id']}/comandas").status_code == 401


def test_bajar_por_debajo_de_lo_enviado_y_volver_a_subir(api, cuenta_con_cocina):
    h, cuenta = cuenta_con_cocina
    hamburguesa = cuenta["items"][0]["id"]
    api.post(f"/cuentas/{cuenta['id']}/comandas", headers=h, json={"items": [{"cuenta_item_id": hamburguesa, "cantidad": 2}]})
    # Cancelan una (queda 1 enviada) y después piden otra: esa sí va a cocina.
    api.patch(f"/cuentas/{cuenta['id']}/items/{hamburguesa}", headers=h, json={"cantidad": 1})
    item = api.patch(f"/cuentas/{cuenta['id']}/items/{hamburguesa}", headers=h, json={"cantidad": 2}).json()["items"][0]
    assert (item["cantidad"], item["enviado"]) == (2, 1)
    r = api.post(f"/cuentas/{cuenta['id']}/comandas", headers=h, json={"items": [{"cuenta_item_id": hamburguesa, "cantidad": 1}]})
    assert r.status_code == 201, r.text
