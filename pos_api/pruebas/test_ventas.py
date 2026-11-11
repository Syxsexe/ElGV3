"""Ventas directas: líneas con foto de precio y costo, pagos, fiado y cupo.

Usan el turno abierto compartido (fixture turno) y artículos propios.
"""
import datetime
import uuid

import pytest

from pos_api.pruebas.test_caja import _abrir


@pytest.fixture
def producto(bd, f):
    """producto(precio, costo, stock) → id de un producto de tienda activo."""
    def _crear(precio=10000, costo=0, stock=100, tipo_categoria="tienda"):
        with bd.transaction():
            pid = f.producto(precio=precio, costo=costo, tipo_categoria=tipo_categoria)
            bd.execute("UPDATE productos SET stock = %s WHERE articulo_id = %s", (stock, pid))
        return pid
    return _crear


def _metodo(f, codigo):
    return str(f.metodo(codigo))


def test_venta_mixta_con_fiado(api, sesion, bd, f, turno, producto):
    h = sesion("vendedor")
    gaseosa, perro = producto(precio=3000, costo=1800, stock=10), producto(precio=12000, costo=5000)
    cliente = f.cliente(limite=50000)
    bd.execute("UPDATE clientes SET dias_credito = 15 WHERE tercero_id = %s", (cliente,))
    esperado_antes = bd.execute(
        "SELECT esperado FROM v_sesion_cajas vs JOIN cajas c ON c.id = vs.caja_id WHERE sesion_id = %s AND c.nombre = 'Efectivo'",
        (turno,)).fetchone()["esperado"]

    r = api.post("/ventas", headers=h, json={
        "sesion_id": str(turno), "cliente_id": str(cliente), "descuento": 1000,
        "lineas": [{"articulo_id": str(gaseosa), "cantidad": 2}, {"articulo_id": str(perro), "cantidad": 1}],
        "pagos": [{"metodo_pago_id": _metodo(f, "efectivo"), "monto": 10000},
                  {"metodo_pago_id": _metodo(f, "nequi"), "monto": 3000}],
        "fiado": 4000})
    assert r.status_code == 201, r.text
    venta = r.json()
    assert (venta["subtotal"], venta["total"], venta["pagado"], venta["fiado"], venta["metodo"]) == (18000, 17000, 13000, 4000, "mixto")
    assert [(l["cantidad"], l["precio_unit"]) for l in venta["lineas"]] == [(2, 3000), (1, 12000)]
    assert [p["metodo"] for p in venta["pagos"]] == ["Efectivo", "Nequi"]
    assert venta["cliente"] and venta["usuario"]

    # Foto del costo, stock descontado, cargo con el vencimiento del cliente.
    costos = [x["costo_unit"] for x in bd.execute(
        "SELECT costo_unit FROM detalle_venta WHERE venta_id = %s ORDER BY id", (venta["id"],))]
    assert costos == [1800, 5000]
    assert bd.execute("SELECT stock FROM productos WHERE articulo_id = %s", (gaseosa,)).fetchone()["stock"] == 8
    cargo = bd.execute("SELECT monto, vence_en FROM cargos_credito WHERE venta_id = %s", (venta["id"],)).fetchone()
    hoy = bd.execute("SELECT current_date AS hoy").fetchone()["hoy"]
    assert (cargo["monto"], cargo["vence_en"]) == (4000, hoy + datetime.timedelta(days=15))
    # El efectivo cobrado entra al esperado de su caja.
    esperado = bd.execute(
        "SELECT esperado FROM v_sesion_cajas vs JOIN cajas c ON c.id = vs.caja_id WHERE sesion_id = %s AND c.nombre = 'Efectivo'",
        (turno,)).fetchone()["esperado"]
    assert esperado - esperado_antes == 10000
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s", (venta["id"],)).fetchone()["detalle"]
    assert detalle.startswith(f"Venta #{venta['numero']} por $17.000")
    assert "Efectivo $10.000, Nequi $3.000, crédito $4.000 a" in detalle and "(descuento $1.000)" in detalle

    assert api.get(f"/ventas/{venta['id']}", headers=h).json()["numero"] == venta["numero"]
    assert api.get(f"/ventas/{uuid.uuid4()}", headers=h).status_code == 404
    cupo = api.get(f"/clientes/{cliente}/cupo", headers=h).json()
    assert (cupo["limite_credito"], cupo["saldo"], cupo["disponible"]) == (50000, 4000, 46000)


def test_la_venta_usa_el_precio_actual(api, sesion, bd, f, turno, producto):
    h = sesion("vendedor")
    pid = producto(precio=5000)
    bd.execute("UPDATE articulos SET precio_venta = 6000 WHERE id = %s", (pid,))
    venta = {"sesion_id": str(turno), "lineas": [{"articulo_id": str(pid), "cantidad": 1}],
             "pagos": [{"metodo_pago_id": _metodo(f, "efectivo"), "monto": 5000}]}
    r = api.post("/ventas", headers=h, json=venta)
    assert (r.status_code, r.json()["detail"]) == (400, "Falta cobrar $1.000: el total es $6.000.")
    venta["pagos"][0]["monto"] = 7000
    r = api.post("/ventas", headers=h, json=venta)
    assert r.status_code == 400 and r.json()["detail"].startswith("Se está cobrando $1.000 de más")
    venta["pagos"][0]["monto"] = 6000
    assert api.post("/ventas", headers=h, json=venta).status_code == 201


def test_venta_rechazada(api, sesion, bd, f, turno, producto):
    h = sesion("vendedor")
    pid = producto(precio=10000)
    efectivo = _metodo(f, "efectivo")
    base = {"sesion_id": str(turno), "lineas": [{"articulo_id": str(pid), "cantidad": 1}],
            "pagos": [{"metodo_pago_id": efectivo, "monto": 10000}]}
    vender = lambda **cambios: api.post("/ventas", headers=h, json=base | cambios)

    r = vender(descuento=12000, pagos=[])
    assert (r.status_code, r.json()["detail"]) == (400, "El descuento ($12.000) supera el subtotal ($10.000).")
    r = vender(lineas=[{"articulo_id": str(uuid.uuid4()), "cantidad": 1}])
    assert (r.status_code, r.json()["detail"]) == (404, "Uno de los artículos no existe.")
    assert vender(lineas=[]).status_code == 422
    assert vender(lineas=[{"articulo_id": str(pid), "cantidad": 0}]).status_code == 422
    assert vender(pagos=[{"metodo_pago_id": efectivo, "monto": 0}]).status_code == 422
    r = vender(pagos=[{"metodo_pago_id": str(uuid.uuid4()), "monto": 10000}])
    assert r.status_code == 400 and "métodos de pago no existe" in r.json()["detail"]
    r = vender(sesion_id=str(uuid.uuid4()))
    assert (r.status_code, r.json()["detail"]) == (404, "El turno de caja no existe.")

    bd.execute("UPDATE articulos SET activo = false WHERE id = %s", (pid,))
    r = vender()
    assert r.status_code == 400 and r.json()["detail"].startswith("Ya no se vende:")
    assert api.post("/ventas", json=base).status_code == 401
    # Nada de lo rechazado quedó a medias.
    assert bd.execute("SELECT count(*) AS n FROM detalle_venta WHERE articulo_id = %s", (pid,)).fetchone()["n"] == 0


def test_fiado_exige_cliente_con_cupo(api, sesion, bd, f, turno, producto):
    h = sesion("vendedor")
    pid = producto(precio=20000)
    sin_cupo, con_cupo = f.cliente(limite=0), f.cliente(limite=30000)
    f.cargo(con_cupo, 15000, notas="Saldo anterior")
    base = {"sesion_id": str(turno), "lineas": [{"articulo_id": str(pid), "cantidad": 1}], "fiado": 20000}
    vender = lambda **cambios: api.post("/ventas", headers=h, json=base | cambios)

    r = vender()
    assert (r.status_code, r.json()["detail"]) == (400, "Para vender a crédito elige el cliente.")
    r = vender(cliente_id=str(sin_cupo))
    assert r.status_code == 400 and "no tiene cupo de crédito" in r.json()["detail"]
    r = vender(cliente_id=str(con_cupo))
    assert r.status_code == 400 and "tiene disponible $15.000 de crédito (cupo $30.000, debe $15.000)" in r.json()["detail"]
    r = vender(cliente_id=str(uuid.uuid4()))
    assert (r.status_code, r.json()["detail"]) == (404, "El cliente no existe.")
    bd.execute("UPDATE clientes SET activo = false WHERE tercero_id = %s", (con_cupo,))
    r = vender(cliente_id=str(con_cupo), fiado=5000, pagos=[{"metodo_pago_id": _metodo(f, "efectivo"), "monto": 15000}])
    assert r.status_code == 400 and "desactivado como cliente" in r.json()["detail"]

    # Fiado puro dentro del cupo.
    bd.execute("UPDATE clientes SET activo = true WHERE tercero_id = %s", (con_cupo,))
    r = vender(cliente_id=str(con_cupo), lineas=[{"articulo_id": str(pid), "cantidad": 0.5}], fiado=10000)
    assert r.status_code == 201, r.text
    assert (r.json()["metodo"], r.json()["fiado"]) == ("credito", 10000)
    assert api.get(f"/clientes/{con_cupo}/cupo", headers=h).json()["disponible"] == 5000
    assert api.get(f"/clientes/{uuid.uuid4()}/cupo", headers=h).status_code == 404


def test_venta_en_turno_cerrado(api, sesion, f, producto):
    """Una pantalla vieja que vende en el turno ya cerrado no cae en el siguiente."""
    h = sesion("vendedor")
    pid = producto(precio=1000)
    viejo = _abrir(api, h)
    _abrir(api, h)  # cierra el viejo y abre el siguiente
    r = api.post("/ventas", headers=h, json={
        "sesion_id": viejo["id"], "lineas": [{"articulo_id": str(pid), "cantidad": 1}],
        "pagos": [{"metodo_pago_id": _metodo(f, "efectivo"), "monto": 1000}]})
    assert (r.status_code, r.json()["detail"]) == (400, f"El turno #{viejo['numero']} ya está cerrado.")


def test_vendibles_por_tipo_de_categoria(api, sesion, bd, producto):
    h = sesion("vendedor")
    tienda, cocina = producto(precio=1111), producto(precio=2222, tipo_categoria="cocina")

    def encontrado(pid, **params):
        nombre = bd.execute("SELECT nombre FROM articulos WHERE id = %s", (pid,)).fetchone()["nombre"]
        return str(pid) in {a["id"] for a in api.get("/catalogo/vendibles", headers=h, params=params | {"q": nombre}).json()}

    assert encontrado(cocina, categoria_tipo="cocina") and not encontrado(tienda, categoria_tipo="cocina")
    assert encontrado(tienda, categoria_tipo="tienda", tipo="producto")
    assert api.get("/catalogo/vendibles", headers=h, params={"categoria_tipo": "bar"}).status_code == 422
