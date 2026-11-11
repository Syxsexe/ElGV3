"""Catálogo: artículos por subtipo, recetas y costos, insumos, preparaciones y stock."""
import uuid

import pytest


def _u(prefijo):
    return f"{prefijo} {uuid.uuid4().hex[:6]}"


@pytest.fixture
def admin(sesion):
    return sesion("admin")


@pytest.fixture
def cat(api, admin):
    """crea categorías: cat("tienda") → id."""
    def _cat(tipo="tienda"):
        return api.post("/catalogo/categorias", headers=admin, json={"nombre": _u("Cat"), "tipo": tipo}).json()["id"]
    return _cat


@pytest.fixture
def unidad(api, admin):
    return {u["simbolo"]: u["id"] for u in api.get("/catalogo/unidades", headers=admin).json()}


def _insumo(api, h, unidad, costo, nombre=None):
    r = api.post("/catalogo/insumos", headers=h, json={"nombre": nombre or _u("Insumo"), "unidad_medida_id": unidad["g"],
                                                        "costo_unitario": str(costo)})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _articulo(api, h, **datos):
    r = api.post("/catalogo/articulos", headers=h, json=datos)
    assert r.status_code == 201, r.text
    return r.json()


def test_producto_de_tienda_con_impuesto_por_defecto_y_stock_inicial(api, admin, cat, bd):
    p = _articulo(api, admin, tipo="producto", nombre=_u("Gaseosa"), categoria_id=cat("tienda"),
                  precio_venta="3500", precio_costo="2000", stock="24", stock_minimo="6", codigo=_u("770"))
    assert (p["impuesto"], p["stock"], p["costo"], p["tiene_receta"]) == ("IVA19", 24, 2000, False)
    detalle = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s", (p["id"],)).fetchone()["detalle"]
    assert "stock inicial 24" in detalle
    repetido = api.post("/catalogo/articulos", headers=admin, json={
        "tipo": "producto", "nombre": "Otra", "categoria_id": cat(), "precio_venta": "1", "codigo": p["codigo"]})
    assert (repetido.status_code, repetido.json()["detail"]) == (400, "Ya existe un producto con ese código.")


def test_plato_con_receta_calcula_su_costo(api, admin, cat, unidad, bd):
    pan, carne = _insumo(api, admin, unidad, "10"), _insumo(api, admin, unidad, "25")
    plato = _articulo(api, admin, tipo="producto", nombre=_u("Hamburguesa"), categoria_id=cat("cocina"),
                      precio_venta="18000", receta=[{"insumo_id": pan, "cantidad": "80"}, {"insumo_id": carne, "cantidad": "150"}])
    assert (plato["impuesto"], plato["costo"], plato["tiene_receta"]) == ("INC8", 4550, True)  # 800 + 3750
    assert len(plato["receta"]) == 2

    # Sube la carne → sube el plato (lo recalcula la base).
    api.patch(f"/catalogo/insumos/{carne}", headers=admin, json={"costo_unitario": "30"})
    assert api.get(f"/catalogo/articulos/{plato['id']}", headers=admin).json()["costo"] == 5300

    # El costo de un plato con receta no se edita a mano; quitando la receta, sí.
    r = api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin, json={"precio_costo": "1000"})
    assert r.status_code == 400 and "se calcula solo" in r.json()["detail"]
    r = api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin, json={"precio_costo": "1000", "receta": []})
    assert (r.json()["costo"], r.json()["tiene_receta"]) == (1000, False)

    # Reenviar la misma receta (la pantalla siempre la manda) no es un cambio.
    n = lambda: bd.execute("SELECT count(*) AS c FROM auditoria WHERE entidad_id = %s", (plato["id"],)).fetchone()["c"]
    antes = n()
    api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin, json={"receta": [], "stock_minimo": "0"})
    assert n() == antes

    dup = api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin,
                    json={"receta": [{"insumo_id": pan, "cantidad": "1"}, {"insumo_id": pan, "cantidad": "2"}]})
    assert dup.status_code == 400 and "repetido" in dup.json()["detail"]
    # Repetidos que "se ven igual" a la receta actual también se rechazan.
    api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin, json={"receta": [{"insumo_id": pan, "cantidad": "80"}]})
    igual = api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin,
                      json={"receta": [{"insumo_id": pan, "cantidad": "80"}, {"insumo_id": pan, "cantidad": "80"}]})
    assert igual.status_code == 400


def test_combo_adicional_y_servicio(api, admin, cat, unidad):
    gaseosa = _articulo(api, admin, tipo="producto", nombre=_u("Gaseosa"), categoria_id=cat(), precio_venta="3500", precio_costo="2000")
    papas = _articulo(api, admin, tipo="producto", nombre=_u("Papas"), categoria_id=cat(), precio_venta="4000", precio_costo="2500")
    combo = _articulo(api, admin, tipo="combo", nombre=_u("Combo"), categoria_id=cat("cocina"), precio_venta="7000",
                      productos=[{"producto_id": gaseosa["id"], "cantidad": "2"}, {"producto_id": papas["id"], "cantidad": "1"}])
    assert (combo["impuesto"], combo["costo"], len(combo["productos"])) == ("INC8", 6500, 2)

    iva = next(i["id"] for i in api.get("/catalogo/impuestos", headers=admin).json() if i["codigo"] == "IVA19")
    r = api.patch(f"/catalogo/articulos/{combo['id']}", headers=admin, json={"impuesto_id": iva})
    assert r.status_code == 400 and "debe llevar un impuesto INC" in r.json()["detail"]
    vacio = api.post("/catalogo/articulos", headers=admin, json={
        "tipo": "combo", "nombre": _u("Combo"), "categoria_id": cat("cocina"), "precio_venta": "1", "productos": []})
    assert vacio.status_code == 400 and "al menos un producto" in vacio.json()["detail"]

    queso = _insumo(api, admin, unidad, "12.5")
    extra = _articulo(api, admin, tipo="adicional", nombre=_u("Queso extra"), categoria_id=cat("cocina"),
                      precio_venta="2000", insumo_id=queso, cantidad="40")
    assert extra["costo"] == 500
    sin_insumo = api.post("/catalogo/articulos", headers=admin, json={
        "tipo": "adicional", "nombre": _u("X"), "categoria_id": cat(), "precio_venta": "1"})
    assert sin_insumo.status_code == 400

    exento = next(i["id"] for i in api.get("/catalogo/impuestos", headers=admin).json() if i["codigo"] == "IVA0-EXENTO")
    servicio = _articulo(api, admin, tipo="servicio", nombre=_u("Alquiler de mesa"), categoria_id=cat(),
                         precio_venta="5000", impuesto_id=exento)
    assert (servicio["impuesto"], servicio["costo"]) == ("IVA0-EXENTO", 0)


def test_vendedor_consulta_precios_sin_ver_costos(api, admin, sesion, cat):
    nombre = _u("Crêpe de Piña")
    _articulo(api, admin, tipo="producto", nombre=nombre, categoria_id=cat("cocina"), precio_venta="15000", precio_costo="6000")
    vendedor = sesion("vendedor")
    encontrados = api.get("/catalogo/vendibles", headers=vendedor, params={"q": "crepe de pina " + nombre[-6:]}).json()
    assert [a["nombre"] for a in encontrados] == [nombre]
    assert "costo" not in encontrados[0] and "precio_costo" not in encontrados[0]
    assert api.get("/catalogo/articulos", headers=vendedor).status_code == 403
    assert api.post("/catalogo/articulos", headers=vendedor, json={
        "tipo": "servicio", "nombre": "X", "categoria_id": cat(), "precio_venta": "1"}).status_code == 403


def test_permiso_de_combos_no_alcanza_para_productos(api, admin, cat, crear_usuario, bd):
    rol = api.post("/roles", headers=admin, json={"nombre": _u("Combos"), "permisos": ["combos.editar"]}).json()["id"]
    uid, nombre = crear_usuario()
    bd.execute("UPDATE usuarios SET rol_id = %s WHERE id = %s", (rol, uid))
    h = {"Authorization": f"Bearer {api.post('/auth/login', json={'usuario': nombre, 'contrasena': 'clave-de-prueba'}).json()['token']}"}
    gaseosa = _articulo(api, admin, tipo="producto", nombre=_u("Gaseosa"), categoria_id=cat(), precio_venta="3500")
    assert api.post("/catalogo/articulos", headers=h, json={
        "tipo": "combo", "nombre": _u("Combo"), "categoria_id": cat("cocina"), "precio_venta": "5000",
        "productos": [{"producto_id": gaseosa["id"], "cantidad": "1"}]}).status_code == 201
    assert api.patch(f"/catalogo/articulos/{gaseosa['id']}", headers=h, json={"precio_venta": "1"}).status_code == 403


def test_ajuste_de_stock_queda_en_auditoria(api, admin, cat, bd):
    p = _articulo(api, admin, tipo="producto", nombre=_u("Sobre"), categoria_id=cat(), precio_venta="5000", stock="10")
    r = api.post(f"/catalogo/articulos/{p['id']}/ajuste-stock", headers=admin, json={"contado": "8", "motivo": "conteo semanal"})
    assert r.json()["stock"] == 8
    ultimo = bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s ORDER BY id DESC LIMIT 1", (p["id"],)).fetchone()
    assert ultimo["detalle"].endswith("10.000 → 8 (conteo semanal)")


def test_preparaciones_anidadas_y_ciclos(api, admin, cat, unidad):
    sal, pollo = _insumo(api, admin, unidad, "2"), _insumo(api, admin, unidad, "20")
    adobo = api.post("/catalogo/preparaciones", headers=admin, json={
        "nombre": _u("Adobo"), "unidad_medida_id": unidad["g"], "rendimiento": "100",
        "receta": [{"insumo_id": sal, "cantidad": "100"}]}).json()
    assert adobo["costo"] == 2
    filete = api.post("/catalogo/preparaciones", headers=admin, json={
        "nombre": _u("Filete"), "unidad_medida_id": unidad["g"], "rendimiento": "500",
        "receta": [{"insumo_id": pollo, "cantidad": "500"}, {"insumo_id": adobo["id"], "cantidad": "50"}]}).json()
    assert filete["costo"] == pytest.approx(20.2)  # (500×20 + 50×2) / 500

    ciclo = api.put(f"/catalogo/preparaciones/{adobo['id']}", headers=admin, json={
        "rendimiento": "100", "receta": [{"insumo_id": filete["id"], "cantidad": "10"}]})
    assert ciclo.status_code == 400 and "ciclo" in ciclo.json()["detail"]

    a_mano = api.patch(f"/catalogo/insumos/{adobo['id']}", headers=admin, json={"costo_unitario": "5"})
    assert a_mano.status_code == 400 and "se calcula" in a_mano.json()["detail"]
    assert api.delete(f"/catalogo/preparaciones/{adobo['id']}", headers=admin).status_code == 200
    assert adobo["id"] not in [p["id"] for p in api.get("/catalogo/preparaciones", headers=admin).json()]


def test_categorias(api, admin, cat):
    c = cat()
    assert api.patch(f"/catalogo/categorias/{c}", headers=admin, json={"tipo": "cocina"}).json()["tipo"] == "cocina"
    _articulo(api, admin, tipo="servicio", nombre=_u("S"), categoria_id=c, precio_venta="1")
    r = api.delete(f"/catalogo/categorias/{c}", headers=admin)
    assert (r.status_code, r.json()["detail"]) == (400, "No se puede borrar: otros registros dependen de este.")
    vacia = cat()
    assert api.delete(f"/catalogo/categorias/{vacia}", headers=admin).status_code == 200


def test_busqueda_sin_tildes_y_literal(api, admin, sesion, cat, unidad):
    sufijo = uuid.uuid4().hex[:6]
    for nombre in (f"Häagen-Dazs {sufijo}", f"Jugo 100% {sufijo}", f"Jugo 1000 {sufijo}"):
        _articulo(api, admin, tipo="producto", nombre=nombre, categoria_id=cat(), precio_venta="1000")
    v = sesion("vendedor")
    buscar = lambda q: [a["nombre"] for a in api.get("/catalogo/vendibles", headers=v, params={"q": q}).json()]
    assert buscar(f"haagen-dazs {sufijo}") == [f"Häagen-Dazs {sufijo}"]
    assert buscar(f"HÄAGEN") and buscar("Häagen") == buscar("haagen")
    assert buscar(f"100% {sufijo}") == [f"Jugo 100% {sufijo}"]  # el % no es comodín
    _insumo(api, admin, unidad, "1", nombre=f"Cebolla Salteáda {sufijo}")
    insumos = api.get("/catalogo/insumos", headers=admin, params={"q": f"cebolla salteada {sufijo}"}).json()
    assert [i["nombre"] for i in insumos] == [f"Cebolla Salteáda {sufijo}"]


def test_quitar_una_preparacion_conserva_su_costo(api, admin, cat, unidad):
    tomate = _insumo(api, admin, unidad, "6")
    salsa = api.post("/catalogo/preparaciones", headers=admin, json={
        "nombre": _u("Salsa BBQ"), "unidad_medida_id": unidad["g"], "rendimiento": "200",
        "receta": [{"insumo_id": tomate, "cantidad": "100"}]}).json()
    assert salsa["costo"] == 3
    plato = _articulo(api, admin, tipo="producto", nombre=_u("Costillas"), categoria_id=cat("cocina"),
                      precio_venta="25000", receta=[{"insumo_id": salsa["id"], "cantidad": "50"}])
    assert plato["costo"] == 150
    api.delete(f"/catalogo/preparaciones/{salsa['id']}", headers=admin)
    assert api.get(f"/catalogo/articulos/{plato['id']}", headers=admin).json()["costo"] == 150


def test_plato_con_insumos_y_productos_de_tienda(api, admin, cat, unidad, bd):
    carne = _insumo(api, admin, unidad, "20")
    pan = _articulo(api, admin, tipo="producto", nombre=_u("Pan"), categoria_id=cat("tienda"), precio_venta="1500",
                    precio_costo="800", stock="4")
    plato = _articulo(api, admin, tipo="producto", nombre=_u("Hamburguesa"), categoria_id=cat("cocina"), precio_venta="18000",
                      receta=[{"insumo_id": carne, "cantidad": "150"}, {"producto_id": pan["id"], "cantidad": "1"}])
    assert (plato["costo"], plato["tiene_receta"]) == (3800, True)  # 150 × 20 + 1 × 800
    lineas = {("insumo" if r["insumo_id"] else "producto"): r for r in plato["receta"]}
    assert (lineas["insumo"]["subtotal"], lineas["producto"]["subtotal"], lineas["producto"]["stock"]) == (3000, 800, 4)
    # Sin stock de carne, alcanza para 0 aunque haya pan.
    assert plato["alcanza"] == 0
    api.post(f"/catalogo/insumos/{carne}/ajuste-stock", headers=admin, json={"contado": "1000", "motivo": "conteo"})
    assert api.get(f"/catalogo/articulos/{plato['id']}", headers=admin).json()["alcanza"] == 4  # el pan limita

    # La misma receta en otro orden no es un cambio; un producto repetido sí se rechaza.
    n = lambda: bd.execute("SELECT count(*) AS c FROM auditoria WHERE entidad_id = %s", (plato["id"],)).fetchone()["c"]
    antes = n()
    api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin,
              json={"receta": [{"producto_id": pan["id"], "cantidad": "1"}, {"insumo_id": carne, "cantidad": "150"}]})
    assert n() == antes
    r = api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin,
                  json={"receta": [{"producto_id": pan["id"], "cantidad": "1"}, {"producto_id": pan["id"], "cantidad": "2"}]})
    assert r.status_code == 400 and "repetido" in r.json()["detail"]
    # Una línea es insumo o producto, no ambos ni ninguno; un plato no va en otro plato.
    r = api.patch(f"/catalogo/articulos/{plato['id']}", headers=admin,
                  json={"receta": [{"insumo_id": carne, "producto_id": pan["id"], "cantidad": "1"}]})
    assert r.status_code == 422
    otro = _articulo(api, admin, tipo="producto", nombre=_u("Papas"), categoria_id=cat("cocina"), precio_venta="5000")
    r = api.patch(f"/catalogo/articulos/{otro['id']}", headers=admin, json={"receta": [{"producto_id": plato["id"], "cantidad": "1"}]})
    assert r.status_code == 400 and "solo van productos de la tienda" in r.json()["detail"]
    # Ya no se compra: tiene receta.
    assert plato["id"] not in [i["id"] for i in api.get("/compras/items", headers=admin, params={"q": plato["nombre"]}).json()]


def test_insumo_con_stock_ajuste_y_produccion(api, admin, cat, unidad, bd):
    tomate = api.post("/catalogo/insumos", headers=admin, json={
        "nombre": _u("Tomate"), "unidad_medida_id": unidad["g"], "costo_unitario": "4", "stock": "5000", "stock_minimo": "1000"}).json()
    assert (tomate["stock"], tomate["stock_minimo"]) == (5000, 1000)
    assert api.patch(f"/catalogo/insumos/{tomate['id']}", headers=admin, json={"stock_minimo": "500"}).json()["stock_minimo"] == 500
    r = api.post(f"/catalogo/insumos/{tomate['id']}/ajuste-stock", headers=admin, json={"contado": "4800", "motivo": "merma"})
    assert r.json()["stock"] == 4800
    assert "4800" in bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s ORDER BY id DESC LIMIT 1",
                                (tomate["id"],)).fetchone()["detalle"]

    salsa = api.post("/catalogo/preparaciones", headers=admin, json={
        "nombre": _u("Salsa"), "unidad_medida_id": unidad["g"], "rendimiento": "2000",
        "receta": [{"insumo_id": tomate["id"], "cantidad": "2500"}]}).json()
    r = api.post(f"/catalogo/preparaciones/{salsa['id']}/producir", headers=admin, json={"lotes": "1.5", "notas": "mañana"})
    assert r.status_code == 201, r.text
    assert r.json()["stock"] == 3000 and r.json()["receta"][0]["stock"] == 1050  # 4800 − 1,5 × 2500
    hechas = api.get(f"/catalogo/preparaciones/{salsa['id']}/producciones", headers=admin).json()
    assert [(p["lotes"], p["cantidad"], p["notas"]) for p in hechas] == [(1.5, 3000, "mañana")]
    assert api.post(f"/catalogo/preparaciones/{tomate['id']}/producir", headers=admin, json={"lotes": "1"}).status_code == 404
    assert api.post(f"/catalogo/preparaciones/{salsa['id']}/producir", headers=admin, json={"lotes": "0"}).status_code == 422


def test_inicio_avisa_insumos_bajos(api, admin, sesion, unidad):
    queso = api.post("/catalogo/insumos", headers=admin, json={
        "nombre": _u("Queso"), "unidad_medida_id": unidad["g"], "stock": "200", "stock_minimo": "500"}).json()
    bajos = api.get("/inicio", headers=sesion("vendedor")).json()["bajo_minimo"]["productos"]
    fila = next(p for p in bajos if p["id"] == queso["id"])
    assert (fila["clase"], fila["unidad"], fila["stock"]) == ("insumo", "g", 200)
