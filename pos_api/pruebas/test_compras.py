"""Compras a proveedores: líneas, stock, último costo, cuentas por pagar y borrado."""
import uuid
from decimal import Decimal

import pytest


@pytest.fixture
def producto(bd, f):
    def _crear(costo=1000, stock=5, tipo_categoria="tienda"):
        with bd.transaction():
            pid = f.producto(costo=costo, tipo_categoria=tipo_categoria)
            bd.execute("UPDATE productos SET stock = %s WHERE articulo_id = %s", (stock, pid))
        return str(pid)
    return _crear


def _compra(proveedor, *lineas, **soporte):
    return {"proveedor_id": str(proveedor), "lineas": list(lineas), **soporte}


def test_compra_mueve_stock_y_costos(api, sesion, bd, f, producto):
    admin = sesion("admin")
    proveedor = f.proveedor()
    gaseosa = producto(costo=1000, stock=5)
    queso = str(f.insumo(costo=2))
    iva = str(f.impuesto("IVA19"))
    lineas = [{"producto_id": gaseosa, "cantidad": 10, "costo_unit": 1500, "impuesto_id": iva},
              {"insumo_id": queso, "cantidad": 1000, "costo_unit": 3.5}]

    r = api.post("/compras", headers=admin, json=_compra(proveedor, *lineas, tipo_soporte="factura_electronica"))
    assert (r.status_code, r.json()["detail"]) == (400, "Una factura electrónica lleva su CUFE.")
    r = api.post("/compras", headers=admin, json=_compra(
        proveedor, *lineas, tipo_soporte="factura", numero_soporte=" FV-77 ", fecha_soporte="2026-11-01"))
    assert r.status_code == 201, r.text
    compra = r.json()
    assert (compra["total"], compra["pendiente"], compra["pagado"], compra["numero_soporte"]) == (18500, 18500, 0, "FV-77")
    assert compra["base"] == round(15000 / 1.19 + 3500, 2)
    assert [(i["tipo"], i["cantidad"], i["impuesto"]) for i in compra["items"]] == [("producto", 10, "IVA19"), ("insumo", 1000, None)]
    assert sorted((c["antes"], c["ahora"]) for c in compra["costos_actualizados"]) == [(2, 3.5), (1000, 1500)]
    assert bd.execute("SELECT stock, precio_costo FROM productos WHERE articulo_id = %s", (gaseosa,)).fetchone() == \
        {"stock": 15, "precio_costo": 1500}
    assert bd.execute("SELECT costo_unitario FROM insumos WHERE id = %s", (queso,)).fetchone()["costo_unitario"] == 3.5
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s", (compra["id"],)).fetchone()["detalle"]
    assert detalle.startswith(f"Registró la compra #{compra['numero']} a") and "por $18.500 (factura FV-77)" in detalle
    assert detalle.endswith("actualizó el costo de 2 producto(s) o insumo(s)")

    # Mismo costo otra vez: no hay nada que actualizar.
    r = api.post("/compras", headers=admin, json=_compra(proveedor, lineas[0]))
    assert r.status_code == 201 and r.json()["costos_actualizados"] == []
    # Mismo número de soporte del mismo proveedor: rechazado.
    r = api.post("/compras", headers=admin, json=_compra(proveedor, lineas[0], tipo_soporte="factura", numero_soporte="FV-77"))
    assert (r.status_code, r.json()["detail"]) == (400, "Ya hay una compra de ese proveedor con ese número de soporte.")

    assert api.get(f"/compras/{compra['id']}", headers=admin).json()["proveedor"]
    assert any(c["id"] == compra["id"] for c in api.get("/compras", headers=admin, params={"pendientes": True}).json())
    por_pagar = api.get("/compras/por-pagar", headers=admin).json()
    fila = next(p for p in por_pagar["proveedores"] if p["proveedor_id"] == str(proveedor))
    assert (fila["pendiente"], fila["compras"]) == (18500 + 15000, 2)


def test_compra_rechazada(api, sesion, bd, f, producto):
    admin, vendedor = sesion("admin"), sesion("vendedor")
    proveedor = f.proveedor()
    linea = {"producto_id": producto(), "cantidad": 1, "costo_unit": 100}
    comprar = lambda *lineas, **extra: api.post("/compras", headers=admin, json=_compra(proveedor, *lineas, **extra))

    assert api.post("/compras", headers=vendedor, json=_compra(proveedor, linea)).status_code == 403
    r = comprar(linea, linea)
    assert r.status_code == 400 and "aparece dos veces" in r.json()["detail"]
    r = comprar({"producto_id": str(uuid.uuid4()), "cantidad": 1, "costo_unit": 100})
    assert (r.status_code, r.json()["detail"]) == (404, "Uno de los productos o insumos no existe.")
    assert comprar({**linea, "insumo_id": str(f.insumo())}).status_code == 422
    assert comprar({**linea, "costo_unit": 0}).status_code == 422
    assert comprar().status_code == 422
    # Lo que no se compra: desactivado, plato con receta, preparación.
    inactivo = producto()
    bd.execute("UPDATE articulos SET activo = false WHERE id = %s", (inactivo,))
    r = comprar({"producto_id": inactivo, "cantidad": 1, "costo_unit": 100})
    assert r.status_code == 400 and r.json()["detail"].startswith("Están desactivados:")
    with bd.transaction():
        plato = f.producto(tipo_categoria="cocina")
        bd.execute("INSERT INTO receta_insumos (producto_id, insumo_id, cantidad) VALUES (%s, %s, 1)", (plato, f.insumo()))
    r = comprar({"producto_id": str(plato), "cantidad": 1, "costo_unit": 100})
    assert r.status_code == 400 and "tienen receta" in r.json()["detail"]
    preparacion = f.insumo()
    bd.execute("INSERT INTO preparaciones (insumo_id, rendimiento) VALUES (%s, 1)", (preparacion,))
    r = comprar({"insumo_id": str(preparacion), "cantidad": 1, "costo_unit": 100})
    assert r.status_code == 400 and "tienen receta" in r.json()["detail"]
    r = api.post("/compras", headers=admin, json=_compra(uuid.uuid4(), linea))
    assert (r.status_code, r.json()["detail"]) == (404, "El proveedor no existe.")
    bd.execute("UPDATE proveedores SET activo = false WHERE tercero_id = %s", (proveedor,))
    r = comprar(linea)
    assert r.status_code == 400 and "desactivado como proveedor" in r.json()["detail"]


def test_items_de_compra(api, sesion, bd, f, producto):
    admin = sesion("admin")
    suelto = producto()
    with bd.transaction():
        plato = f.producto(tipo_categoria="cocina")
        bd.execute("INSERT INTO receta_insumos (producto_id, insumo_id, cantidad) VALUES (%s, %s, 1)",
                   (plato, f.insumo()))
    insumo = str(f.insumo())
    nombres = {i: bd.execute(f"SELECT nombre FROM {t} WHERE id = %s", (i,)).fetchone()["nombre"]
               for i, t in ((suelto, "articulos"), (str(plato), "articulos"), (insumo, "insumos"))}
    buscar = lambda i: [x["id"] for x in api.get("/compras/items", headers=admin, params={"q": nombres[i]}).json()]
    assert buscar(suelto) == [suelto] and buscar(insumo) == [insumo]
    assert buscar(str(plato)) == []  # su costo lo calcula la receta
    assert api.get("/compras/items", headers=sesion("vendedor")).status_code == 403


def test_borrar_compra_devuelve_el_stock(api, sesion, bd, f, turno, producto):
    admin = sesion("admin")
    proveedor = f.proveedor()
    pid = producto(stock=5)
    linea = {"producto_id": pid, "cantidad": 4, "costo_unit": 100}
    compra = api.post("/compras", headers=admin, json=_compra(proveedor, linea)).json()
    assert bd.execute("SELECT stock FROM productos WHERE articulo_id = %s", (pid,)).fetchone()["stock"] == 9
    assert api.delete(f"/compras/{compra['id']}", headers=admin).status_code == 204
    assert bd.execute("SELECT stock FROM productos WHERE articulo_id = %s", (pid,)).fetchone()["stock"] == 5
    assert api.get(f"/compras/{compra['id']}", headers=admin).status_code == 404
    assert api.delete(f"/compras/{compra['id']}", headers=admin).status_code == 404

    # Con un pago no se borra.
    pagada = api.post("/compras", headers=admin, json=_compra(proveedor, linea)).json()
    r = api.post("/egresos", headers=admin, json={"sesion_id": str(turno), "concepto": "Pago", "compra_id": pagada["id"],
                                                  "pagos": [{"metodo_pago_id": str(f.metodo("efectivo")), "monto": 100}]})
    assert r.status_code == 201, r.text
    r = api.delete(f"/compras/{pagada['id']}", headers=admin)
    assert r.status_code == 400 and "tiene pagos registrados" in r.json()["detail"]


def test_el_costo_se_redondea_como_la_columna(api, sesion, bd, f, producto):
    admin = sesion("admin")
    pid = producto(costo=1000.13)
    linea = {"producto_id": pid, "cantidad": 1, "costo_unit": 1000.125}
    r = api.post("/compras", headers=admin, json=_compra(f.proveedor(), linea))
    # 1000.125 se guarda como 1000.13 (la mitad se aleja del cero): no cambió nada.
    assert r.status_code == 201 and r.json()["costos_actualizados"] == []
    r = api.post("/compras", headers=admin, json=_compra(f.proveedor(), {**linea, "costo_unit": 1000.135}))
    assert [(c["antes"], c["ahora"]) for c in r.json()["costos_actualizados"]] == [(1000.13, 1000.14)]
    assert bd.execute("SELECT precio_costo FROM productos WHERE articulo_id = %s", (pid,)).fetchone()["precio_costo"] == Decimal("1000.14")
