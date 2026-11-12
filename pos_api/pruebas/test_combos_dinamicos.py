"""Combos con grupos de elección: armarlos, venderlos, cuentas y comandas.

El combo de las pruebas: papas fijas y un grupo "Bebida" con Coca-Cola, Pepsi
y cerveza (+$2.000). Usan el turno abierto compartido.
"""
import uuid

import pytest


def _u(prefijo):
    return f"{prefijo} {uuid.uuid4().hex[:6]}"


@pytest.fixture
def admin(sesion):
    return sesion("admin")


@pytest.fixture
def armar(api, admin, bd, f):
    """armar() → (combo, {papas, coca, pepsi, cerveza}) creados por la API."""
    def _armar(stock_coca=10, precio=12000):
        ids = {}
        with bd.transaction():
            for nombre, costo, stock in (("papas", 1000, 50), ("coca", 1500, stock_coca), ("pepsi", 1400, 10),
                                         ("cerveza", 2500, 10)):
                ids[nombre] = f.producto(precio=4000, costo=costo)
                bd.execute("UPDATE productos SET stock = %s WHERE articulo_id = %s", (stock, ids[nombre]))
        r = api.post("/catalogo/articulos", headers=admin, json={
            "tipo": "combo", "nombre": _u("Combo"), "categoria_id": str(f.categoria("cocina")), "precio_venta": precio,
            "productos": [{"producto_id": str(ids["papas"]), "cantidad": 1}],
            "grupos": [{"nombre": "Bebida", "opciones": [
                {"producto_id": str(ids["coca"])}, {"producto_id": str(ids["pepsi"])},
                {"producto_id": str(ids["cerveza"]), "recargo": 2000}]}]})
        assert r.status_code == 201, r.text
        return r.json(), ids
    return _armar


def _stock(bd, producto):
    return bd.execute("SELECT stock FROM productos WHERE articulo_id = %s", (producto,)).fetchone()["stock"]


def _efectivo(f):
    return str(f.metodo("efectivo"))


def _eleccion(combo, producto):
    return [{"grupo_id": combo["grupos"][0]["id"], "producto_id": str(producto)}]


def test_armar_combo_con_grupos(api, admin, armar, f):
    combo, ids = armar()
    assert (combo["costo"], combo["costo_max"], combo["tiene_grupos"], combo["bloqueo"]) == (2400, 3500, True, None)
    grupo = combo["grupos"][0]
    assert (grupo["nombre"], grupo["cantidad"]) == ("Bebida", 1)
    assert sorted((o["recargo"], o["costo_unit"]) for o in grupo["opciones"]) == [(0, 1400), (0, 1500), (2000, 2500)]
    assert grupo["opciones"][-1]["recargo"] == 2000  # las de recargo van al final
    assert combo["alcanza"] == 30  # papas 50; bebidas 10 + 10 + 10

    # Editar: dos unidades de bebida y sin la cerveza; sin cambios no audita.
    r = api.patch(f"/catalogo/articulos/{combo['id']}", headers=admin, json={"grupos": [
        {"nombre": "Bebida", "cantidad": 2, "opciones": [{"producto_id": str(ids["coca"])}]}]})
    assert r.status_code == 200, r.text
    assert (r.json()["costo"], r.json()["costo_max"], r.json()["alcanza"]) == (4000, 4000, 5)

    for grupos, mensaje in [
        ([{"nombre": "Bebida", "opciones": [{"producto_id": str(ids["coca"])}]},
          {"nombre": " bebida ", "opciones": [{"producto_id": str(ids["pepsi"])}]}], "se llaman igual"),
        ([{"nombre": "Bebida", "opciones": [{"producto_id": str(ids["coca"])}, {"producto_id": str(ids["coca"])}]}],
         "repetido"),
    ]:
        r = api.patch(f"/catalogo/articulos/{combo['id']}", headers=admin, json={"grupos": grupos})
        assert r.status_code == 400 and mensaje in r.json()["detail"], r.text
    assert api.patch(f"/catalogo/articulos/{combo['id']}", headers=admin,
                     json={"grupos": [{"nombre": "Bebida", "opciones": []}]}).status_code == 422
    # Sin fijos ni grupos queda vacío.
    r = api.patch(f"/catalogo/articulos/{combo['id']}", headers=admin, json={"productos": [], "grupos": []})
    assert r.status_code == 400 and "al menos un producto fijo o un grupo" in r.json()["detail"]
    # Solo grupos, sin fijos, sí vale.
    r = api.patch(f"/catalogo/articulos/{combo['id']}", headers=admin, json={"productos": []})
    assert r.status_code == 200 and r.json()["productos"] == []


def test_vender_con_eleccion_y_recargo(api, sesion, armar, bd, f, turno):
    combo, ids = armar()
    h = sesion("vendedor")
    opciones = api.get(f"/catalogo/vendibles/{combo['id']}/opciones", headers=h).json()
    assert [o["disponibles"] for o in opciones["grupos"][0]["opciones"]] == [10, 10, 10]
    assert "costo_unit" not in opciones["grupos"][0]["opciones"][0]

    r = api.post("/ventas", headers=h, json={
        "sesion_id": str(turno), "pagos": [{"metodo_pago_id": _efectivo(f), "monto": 28000}],
        "lineas": [{"articulo_id": combo["id"], "cantidad": 2, "elecciones": _eleccion(combo, ids["cerveza"])}]})
    assert r.status_code == 201, r.text
    linea = r.json()["lineas"][0]
    assert (linea["precio_unit"], linea["subtotal"]) == (14000, 28000)
    assert linea["nombre"].endswith(" — " + bd.execute("SELECT nombre FROM articulos WHERE id = %s",
                                                        (ids["cerveza"],)).fetchone()["nombre"])
    assert (_stock(bd, ids["papas"]), _stock(bd, ids["cerveza"]), _stock(bd, ids["coca"])) == (48, 8, 10)
    costo = bd.execute("SELECT costo_unit FROM detalle_venta WHERE venta_id = %s", (r.json()["id"],)).fetchone()
    assert costo["costo_unit"] == 3500  # papas 1000 + cerveza 2500


def test_vender_sin_elegir_o_con_opcion_invalida(api, sesion, armar, bd, f, turno):
    combo, ids = armar()
    h = sesion("vendedor")

    def vender(elecciones):
        return api.post("/ventas", headers=h, json={
            "sesion_id": str(turno), "pagos": [{"metodo_pago_id": _efectivo(f), "monto": 12000}],
            "lineas": [{"articulo_id": combo["id"], "cantidad": 1, "elecciones": elecciones}]})

    r = vender([])
    assert (r.status_code, r.json()["detail"]) == (400, f"Elige Bebida para {combo['nombre']}.")
    r = vender(_eleccion(combo, ids["papas"]))
    assert r.status_code == 400 and "ya no está en Bebida" in r.json()["detail"]
    bd.execute("UPDATE articulos SET activo = false WHERE id = %s", (ids["pepsi"],))
    r = vender(_eleccion(combo, ids["pepsi"]))
    assert r.status_code == 400 and "ya no se vende: elige otra opción de Bebida" in r.json()["detail"]
    opciones = api.get(f"/catalogo/vendibles/{combo['id']}/opciones", headers=h).json()
    assert len(opciones["grupos"][0]["opciones"]) == 2  # la Pepsi ya no se ofrece
    # Un producto no lleva elecciones.
    r = api.post("/ventas", headers=h, json={
        "sesion_id": str(turno), "pagos": [{"metodo_pago_id": _efectivo(f), "monto": 4000}],
        "lineas": [{"articulo_id": str(ids["coca"]), "cantidad": 1, "elecciones": _eleccion(combo, ids["coca"])}]})
    assert r.status_code == 400 and "no es un combo" in r.json()["detail"]


def test_producto_fijo_desactivado_bloquea_el_combo(api, sesion, armar, bd, f, turno):
    combo, ids = armar()
    h = sesion("vendedor")
    bd.execute("UPDATE articulos SET activo = false WHERE id = %s", (ids["papas"],))
    vendible = next(a for a in api.get("/catalogo/vendibles", headers=h, params={"tipo": "combo", "limite": 200}).json()
                    if a["id"] == combo["id"])
    assert vendible["bloqueo"].endswith("está desactivado")
    r = api.post("/ventas", headers=h, json={
        "sesion_id": str(turno), "pagos": [{"metodo_pago_id": _efectivo(f), "monto": 12000}],
        "lineas": [{"articulo_id": combo["id"], "cantidad": 1, "elecciones": _eleccion(combo, ids["coca"])}]})
    assert r.status_code == 400 and "No se puede vender" in r.json()["detail"] and "Inventario" in r.json()["detail"]
    assert api.get(f"/catalogo/vendibles/{combo['id']}/opciones", headers=h).status_code == 400
    cuenta = api.post("/cuentas", headers=h, json={"alias": _u("Mesa")}).json()
    r = api.post(f"/cuentas/{cuenta['id']}/items", headers=h,
                 json={"articulo_id": combo["id"], "elecciones": _eleccion(combo, ids["coca"])})
    assert r.status_code == 400 and "está desactivado" in r.json()["detail"]


def test_cuenta_junta_lo_igual_y_cobra_con_lo_elegido(api, sesion, armar, bd, f, turno):
    combo, ids = armar(stock_coca=3)
    h = sesion("vendedor")
    cuenta = api.post("/cuentas", headers=h, json={"alias": _u("Mesa")}).json()
    url = f"/cuentas/{cuenta['id']}/items"
    for producto in ("coca", "coca", "cerveza"):
        r = api.post(url, headers=h, json={"articulo_id": combo["id"], "elecciones": _eleccion(combo, ids[producto])})
        assert r.status_code == 201, r.text
    items = r.json()["items"]
    assert [(i["cantidad"], i["precio_unit"]) for i in items] == [(2, 12000), (1, 14000)]
    assert items[0]["elecciones"] and items[0]["nombre"].endswith(items[0]["elecciones"])

    # Subir la Coca-Cola a 4 pasa del stock (hay 3) contando lo elegido.
    r = api.patch(f"{url}/{items[0]['id']}", headers=h, json={"cantidad": 4})
    assert r.status_code == 400 and "la cuenta lleva 4" in r.json()["detail"]

    r = api.post(f"/cuentas/{cuenta['id']}/cobrar", headers=h, json={
        "sesion_id": str(turno), "pagos": [{"metodo_pago_id": _efectivo(f), "monto": 38000}]})
    assert r.status_code == 201, r.text
    assert [l["elecciones"] for l in r.json()["lineas"]] == [items[0]["elecciones"], items[1]["elecciones"]]
    assert (_stock(bd, ids["coca"]), _stock(bd, ids["cerveza"]), _stock(bd, ids["papas"])) == (1, 9, 47)


def test_comanda_muestra_lo_elegido(api, sesion, admin, bd, f):
    h = sesion("vendedor")
    with bd.transaction():
        perro, hamburguesa = (f.producto(precio=12000, tipo_categoria="cocina", impuesto="INC8") for _ in range(2))
    combo = api.post("/catalogo/articulos", headers=admin, json={
        "tipo": "combo", "nombre": _u("Combo plato"), "categoria_id": str(f.categoria("cocina")), "precio_venta": 15000,
        "grupos": [{"nombre": "Plato", "opciones": [{"producto_id": str(perro)}, {"producto_id": str(hamburguesa)}]}]})
    assert combo.status_code == 201, combo.text
    combo = combo.json()
    cuenta = api.post("/cuentas", headers=h, json={"alias": _u("Mesa")}).json()
    cuenta = api.post(f"/cuentas/{cuenta['id']}/items", headers=h,
                      json={"articulo_id": combo["id"], "elecciones": _eleccion(combo, hamburguesa)}).json()
    item = cuenta["items"][0]
    assert item["de_cocina"]  # lo elegido es de cocina aunque el combo no tenga fijos
    r = api.post(f"/cuentas/{cuenta['id']}/comandas", headers=h,
                 json={"items": [{"cuenta_item_id": item["id"], "cantidad": 1}]})
    assert r.status_code == 201, r.text
    impreso = r.json()["items"][0]
    nombre = bd.execute("SELECT nombre FROM articulos WHERE id = %s", (hamburguesa,)).fetchone()["nombre"]
    assert (impreso["elecciones"], impreso["nombre"]) == (nombre, f"{combo['nombre']} — {nombre}")


def test_documentos_no_aceptan_combos_con_grupos_todavia(api, sesion, armar):
    combo, _ = armar()
    h = sesion("admin")
    r = api.post("/documentos", headers=h, json={
        "tipo": "cotizacion", "items": [{"articulo_id": combo["id"], "cantidad": 1}]})
    assert r.status_code == 400 and "no en documentos" in r.json()["detail"], r.text
