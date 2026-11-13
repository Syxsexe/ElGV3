"""Toppings de los platos: configurarlos, venderlos, cuentas y comandas.

El plato de las pruebas: un ramen ($15.000) que acepta huevo duro ($2.000,
1 und de huevo) y queso ($3.000, 30 g). Usan el turno abierto compartido.
"""
import uuid

import pytest


def _u(prefijo):
    return f"{prefijo} {uuid.uuid4().hex[:6]}"


@pytest.fixture
def admin(sesion):
    return sesion("admin")


@pytest.fixture
def ramen(api, admin, bd, f):
    """ramen() → (plato, {huevo, queso} adicionales, {huevo, queso} insumos)."""
    def _crear():
        cocina = str(f.categoria("cocina"))
        with bd.transaction():
            insumos = {"huevo": f.insumo(costo=600, unidad="und"), "queso": f.insumo(costo=20)}
            bd.execute("UPDATE insumos SET stock = 100 WHERE id = ANY(%s)", (list(insumos.values()),))
        tops = {}
        for clave, precio, porcion in (("huevo", 2000, 1), ("queso", 3000, 30)):
            r = api.post("/catalogo/articulos", headers=admin, json={
                "tipo": "adicional", "nombre": _u(f"Topping {clave}"), "categoria_id": cocina, "precio_venta": precio,
                "insumo_id": str(insumos[clave]), "cantidad": porcion})
            assert r.status_code == 201, r.text
            tops[clave] = r.json()["id"]
        r = api.post("/catalogo/articulos", headers=admin, json={
            "tipo": "producto", "nombre": _u("Ramen"), "categoria_id": cocina, "precio_venta": 15000,
            "toppings": [tops["huevo"], tops["queso"]]})
        assert r.status_code == 201, r.text
        return r.json(), tops, insumos
    return _crear


def _efectivo(f):
    return str(f.metodo("efectivo"))


def _stock(bd, insumo):
    return bd.execute("SELECT stock FROM insumos WHERE id = %s", (insumo,)).fetchone()["stock"]


def test_configurar_toppings_del_plato(api, admin, ramen, bd):
    plato, tops, _ = ramen()
    assert plato["tiene_toppings"] is True
    assert [(t["precio"], t["porcion"], t["costo"]) for t in plato["toppings"]] == [(2000, 1, 600), (3000, 30, 600)]
    # Los toppings no salen sueltos en la venta; el plato sí, marcado.
    vendibles = {a["id"]: a for a in api.get("/catalogo/vendibles", headers=admin, params={"q": "Topping"}).json()}
    assert tops["huevo"] not in vendibles and tops["queso"] not in vendibles
    lista = api.get("/catalogo/vendibles", headers=admin, params={"q": plato["nombre"]}).json()
    assert lista[0]["tiene_toppings"] is True
    para_vender = api.get(f"/catalogo/vendibles/{plato['id']}/toppings", headers=admin).json()
    assert [t["precio"] for t in para_vender["toppings"]] == [2000, 3000] and "costo" not in para_vender["toppings"][0]

    # Quitar uno queda auditado; un topping que no es adicional no se acepta.
    r = api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin, json={"toppings": [tops["queso"]]})
    assert [t["adicional_id"] for t in r.json()["toppings"]] == [tops["queso"]]
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s ORDER BY id DESC LIMIT 1",
                         (plato["id"],)).fetchone()["detalle"]
    assert detalle.endswith("toppings")
    r = api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin, json={"toppings": [plato["id"]]})
    assert r.status_code == 400 and "no es un adicional" in r.json()["detail"]


def test_vender_un_plato_con_toppings(api, sesion, ramen, bd, f, turno):
    plato, tops, insumos = ramen()
    h = sesion("vendedor")
    r = api.post("/ventas", headers=h, json={
        "sesion_id": str(turno), "pagos": [{"metodo_pago_id": _efectivo(f), "monto": 55000}],
        "lineas": [{"articulo_id": plato["id"], "cantidad": 2, "toppings": [tops["huevo"], tops["queso"]]},
                   {"articulo_id": plato["id"], "cantidad": 1}]})
    assert r.status_code == 201, r.text
    venta = r.json()
    con, sin = venta["lineas"]
    assert (con["precio_unit"], sin["precio_unit"], venta["total"]) == (20000, 15000, 55000)
    assert con["nombre"].startswith(plato["nombre"] + " — con Topping")
    assert sin["nombre"] == plato["nombre"]
    # 2 huevos y 60 g de queso; el costo de la línea suma el de los toppings.
    assert (_stock(bd, insumos["huevo"]), _stock(bd, insumos["queso"])) == (98, 40)
    costos = [x["costo_unit"] for x in bd.execute(
        "SELECT costo_unit FROM detalle_venta WHERE venta_id = %s ORDER BY id", (venta["id"],))]
    assert costos == [1200, 0]


def test_toppings_invalidos(api, sesion, ramen, bd, f, turno):
    plato, tops, _ = ramen()
    h = sesion("vendedor")

    def vender(articulo, toppings):
        return api.post("/ventas", headers=h, json={
            "sesion_id": str(turno), "pagos": [{"metodo_pago_id": _efectivo(f), "monto": 15000}],
            "lineas": [{"articulo_id": articulo, "cantidad": 1, "toppings": toppings}]})
    r = vender(plato["id"], [tops["huevo"], tops["huevo"]])
    assert r.status_code == 400 and "dos veces" in r.json()["detail"]
    otro, otros, _ = ramen()
    r = vender(plato["id"], [otros["huevo"]])
    assert r.status_code == 400 and "ya no está" in r.json()["detail"]
    with bd.transaction():
        gaseosa = f.producto(precio=3000)
    r = vender(str(gaseosa), [tops["huevo"]])
    assert r.status_code == 400 and "no lleva toppings" in r.json()["detail"]
    bd.execute("UPDATE articulos SET activo = false WHERE id = %s", (tops["queso"],))
    r = vender(plato["id"], [tops["queso"]])
    assert r.status_code == 400 and "ya no se vende" in r.json()["detail"]
    # Desactivado no se ofrece al vender.
    assert [t["adicional_id"] for t in api.get(f"/catalogo/vendibles/{plato['id']}/toppings", headers=h).json()["toppings"]] == [tops["huevo"]]


def test_cuenta_junta_lo_igual_comanda_y_cobra_con_toppings(api, sesion, ramen, bd, f, turno):
    plato, tops, insumos = ramen()
    h = sesion("vendedor")
    cuenta = api.post("/cuentas", headers=h, json={"alias": _u("Mesa")}).json()
    url = f"/cuentas/{cuenta['id']}/items"
    con_huevo = {"articulo_id": plato["id"], "toppings": [tops["huevo"]]}
    api.post(url, headers=h, json=con_huevo)
    api.post(url, headers=h, json=con_huevo)  # igual: suma
    c = api.post(url, headers=h, json={"articulo_id": plato["id"]}).json()  # sin toppings: otra línea
    items = sorted(c["items"], key=lambda i: -i["precio_unit"])
    assert [(i["cantidad"], i["precio_unit"]) for i in items] == [(2, 17000), (1, 15000)]
    assert items[0]["nombre"].startswith(plato["nombre"] + " — con Topping huevo")

    # La comanda lleva los toppings junto al nombre.
    comanda = api.post(f"/cuentas/{cuenta['id']}/comandas", headers=h, json={
        "items": [{"cuenta_item_id": items[0]["id"], "cantidad": 2}]}).json()
    assert "con Topping huevo" in comanda["items"][0]["nombre"]

    r = api.post(f"/cuentas/{cuenta['id']}/cobrar", headers=h, json={
        "sesion_id": str(turno), "pagos": [{"metodo_pago_id": _efectivo(f), "monto": 49000}]})
    assert r.status_code == 201, r.text
    venta = r.json()
    assert venta["total"] == 49000 and any("con Topping huevo" in l["nombre"] for l in venta["lineas"])
    assert _stock(bd, insumos["huevo"]) == 98
    assert bd.execute("SELECT count(*) AS n FROM detalle_venta_toppings t JOIN detalle_venta d ON d.id = t.detalle_id "
                      "WHERE d.venta_id = %s", (venta["id"],)).fetchone()["n"] == 1


def test_reglas_de_los_toppings(api, sesion, admin, ramen, bd, f, turno):
    plato, tops, _ = ramen()
    h = sesion("vendedor")
    # Un topping no se vende suelto, ni en venta directa ni en una cuenta.
    r = api.post("/ventas", headers=h, json={
        "sesion_id": str(turno), "pagos": [{"metodo_pago_id": _efectivo(f), "monto": 2000}],
        "lineas": [{"articulo_id": tops["huevo"], "cantidad": 1}]})
    assert r.status_code == 400 and "es un topping" in r.json()["detail"]
    cuenta = api.post("/cuentas", headers=h, json={"alias": _u("Mesa")}).json()
    r = api.post(f"/cuentas/{cuenta['id']}/items", headers=h, json={"articulo_id": tops["huevo"]})
    assert r.status_code == 400 and "es un topping" in r.json()["detail"]

    # Un topping con otro impuesto que el plato no se acepta (se cobra con el del plato).
    iva = str(f.impuesto("IVA19"))
    r = api.post("/catalogo/articulos", headers=admin, json={
        "tipo": "adicional", "nombre": _u("Topping iva"), "categoria_id": str(f.categoria("cocina")), "precio_venta": 1000,
        "impuesto_id": iva, "insumo_id": str(f.insumo()), "cantidad": 1})
    r = api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin, json={"toppings": [tops["huevo"], r.json()["id"]]})
    assert r.status_code == 400 and "otro impuesto" in r.json()["detail"]

    # Quitarle los toppings y pasarlo a tienda en la misma edición se puede.
    r = api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin,
                  json={"toppings": [], "categoria_id": str(f.categoria("tienda"))})
    assert r.status_code == 200, r.text
    assert r.json()["toppings"] == [] and r.json()["categoria_tipo"] == "tienda"
