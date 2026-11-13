"""Conteo físico desde la pantalla: ajusta stock y mínimos en una sola
transacción, y no pisa lo que cambió mientras se contaba."""
import uuid

import pytest

from pos_api.pruebas.test_catalogo import _articulo, _insumo, _u


@pytest.fixture
def admin(sesion):
    return sesion("admin")


@pytest.fixture
def cat(api, admin):
    def _cat(tipo="tienda"):
        return api.post("/catalogo/categorias", headers=admin, json={"nombre": _u("Cat"), "tipo": tipo}).json()["id"]
    return _cat


@pytest.fixture
def unidad(api, admin):
    return {u["simbolo"]: u["id"] for u in api.get("/catalogo/unidades", headers=admin).json()}


def _producto(api, admin, cat, stock="10"):
    return _articulo(api, admin, tipo="producto", nombre=_u("Sobre"), categoria_id=cat(), precio_venta="5000", stock=stock)


def test_conteo_de_productos(api, admin, cat, bd):
    a, b, c = (_producto(api, admin, cat) for _ in range(3))
    r = api.post("/catalogo/conteo/productos", headers=admin, json={"filas": [
        {"id": a["id"], "stock_visto": "10", "contado": "7", "stock_minimo": "3"},   # ajusta y fija mínimo
        {"id": b["id"], "stock_visto": "10", "contado": "10"},                       # contó lo mismo: nada
        {"id": c["id"], "stock_visto": "10", "stock_minimo": "2"},                   # solo el mínimo
    ]})
    assert r.status_code == 200, r.text
    res = r.json()
    assert [(x["nombre"], x["antes"], x["despues"]) for x in res["ajustados"]] == [(a["nombre"], 10, 7)]
    assert sorted(x["nombre"] for x in res["minimos"]) == sorted([a["nombre"], c["nombre"]])
    assert res["cambiaron"] == []
    estado = lambda p: bd.execute("SELECT stock, stock_minimo FROM productos WHERE articulo_id = %s", (p["id"],)).fetchone()
    assert (estado(a)["stock"], estado(a)["stock_minimo"]) == (7, 3)
    assert estado(b)["stock"] == 10 and estado(c)["stock_minimo"] == 2
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s AND detalle LIKE 'Ajustó%%'", (a["id"],)).fetchone()["detalle"]
    assert detalle.endswith("10.000 → 7 (conteo físico)")


def test_lo_que_cambio_mientras_se_contaba_no_se_pisa(api, admin, cat, bd):
    p = _producto(api, admin, cat)
    bd.execute("UPDATE productos SET stock = 8 WHERE articulo_id = %s", (p["id"],))  # se vendieron 2
    res = api.post("/catalogo/conteo/productos", headers=admin, json={"filas": [
        {"id": p["id"], "stock_visto": "10", "contado": "10", "stock_minimo": "4"}]}).json()
    assert res["ajustados"] == []
    assert [(x["visto"], x["actual"]) for x in res["cambiaron"]] == [(10, 8)]
    fila = bd.execute("SELECT stock, stock_minimo FROM productos WHERE articulo_id = %s", (p["id"],)).fetchone()
    assert (fila["stock"], fila["stock_minimo"]) == (8, 4)  # el stock se respeta; el mínimo sí se guarda


def test_conteo_de_insumos_corrige_negativos(api, admin, unidad, bd):
    queso = _insumo(api, admin, unidad, "24.667")
    bd.execute("UPDATE insumos SET stock = -150 WHERE id = %s", (queso,))
    res = api.post("/catalogo/conteo/insumos", headers=admin, json={"filas": [
        {"id": queso, "stock_visto": "-150", "contado": "2500.5", "stock_minimo": "500"}]}).json()
    assert [(x["antes"], x["despues"]) for x in res["ajustados"]] == [(-150, 2500.5)]
    fila = bd.execute("SELECT stock, stock_minimo, costo_unitario FROM insumos WHERE id = %s", (queso,)).fetchone()
    assert (fila["stock"], fila["stock_minimo"], float(fila["costo_unitario"])) == (2500.5, 500, 24.667)


def test_bordes_del_conteo(api, admin, cat, sesion):
    p = _producto(api, admin, cat)
    plato = _articulo(api, admin, tipo="producto", nombre=_u("Plato"), categoria_id=cat("cocina"), precio_venta="9000")
    r = api.post("/catalogo/conteo/productos", headers=admin, json={"filas": [{"id": plato["id"], "stock_visto": "0", "contado": "3"}]})
    assert r.status_code == 400 and "no lleva stock" in r.json()["detail"]
    fila = {"id": p["id"], "stock_visto": "10", "contado": "9"}
    r = api.post("/catalogo/conteo/productos", headers=admin, json={"filas": [fila, fila]})
    assert r.status_code == 400 and "dos veces" in r.json()["detail"]
    r = api.post("/catalogo/conteo/productos", headers=admin, json={"filas": [{**fila, "id": str(uuid.uuid4())}]})
    assert r.status_code == 404
    assert api.post("/catalogo/conteo/productos", headers=admin, json={"filas": [{**fila, "contado": "-1"}]}).status_code == 422
    assert api.post("/catalogo/conteo/productos", headers=admin, json={"filas": []}).status_code == 422
    assert api.post("/catalogo/conteo/productos", headers=sesion("vendedor"), json={"filas": [fila]}).status_code == 403
