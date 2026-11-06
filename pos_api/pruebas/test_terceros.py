"""Clientes y proveedores: documentos, roles, permisos y vínculo con usuarios."""
import random
import uuid

import pytest


def _doc():
    return str(random.randint(10**8, 10**10))


@pytest.fixture
def admin(sesion):
    return sesion("admin")


@pytest.fixture
def vendedor(sesion):
    return sesion("vendedor")


def _crear(api, h, **datos):
    datos.setdefault("nombre", f"Persona {uuid.uuid4().hex[:6]}")
    return api.post("/terceros", headers=h, json=datos)


def test_cajero_registra_clientes_sin_cupo(api, vendedor, admin, bd):
    r = _crear(api, vendedor, tipo_identificacion="13", numero_identificacion="1.085.000." + _doc()[-3:], cliente={})
    assert r.status_code == 201, r.text
    c = r.json()
    assert (c["es_cliente"], c["limite_credito"], c["dias_credito"], c["numero_identificacion"].isdigit()) == (True, 0, 30, True)

    nombre = f"Con cupo {uuid.uuid4().hex[:6]}"
    con_cupo = _crear(api, vendedor, nombre=nombre, cliente={"limite_credito": "200000"})
    assert con_cupo.status_code == 403
    # Todo o nada: el tercero tampoco quedó creado.
    assert bd.execute("SELECT count(*) AS n FROM terceros WHERE nombre = %s", (nombre,)).fetchone()["n"] == 0
    assert api.put(f"/terceros/{c['id']}/cliente", headers=vendedor, json={"limite_credito": "50000"}).status_code == 403
    r = api.put(f"/terceros/{c['id']}/cliente", headers=admin, json={"limite_credito": "50000", "dias_credito": 15})
    assert (r.json()["limite_credito"], r.json()["dias_credito"]) == (50000, 15)


def test_documentos(api, admin):
    nit = _doc()[:9]
    from pos_api.servicios.comun import digito_verificacion
    dv = digito_verificacion(nit)
    r = _crear(api, admin, tipo_persona="juridica", tipo_identificacion="31", numero_identificacion=f"{nit}-{dv}")
    assert (r.status_code, r.json()["numero_identificacion"], r.json()["dv"]) == (201, nit, dv)

    otro = _doc()[:9]
    malo = _crear(api, admin, tipo_identificacion="31", numero_identificacion=f"{otro}-{(digito_verificacion(otro) + 1) % 10}")
    assert malo.status_code == 400 and "dígito de verificación no coincide" in malo.json()["detail"]
    letras = _crear(api, admin, tipo_identificacion="13", numero_identificacion="12AB34")
    assert letras.status_code == 400 and "solo dígitos" in letras.json()["detail"]
    pasaporte = _crear(api, admin, tipo_identificacion="41", numero_identificacion="AB" + _doc())
    assert pasaporte.status_code == 201
    repetido = _crear(api, admin, tipo_identificacion="31", numero_identificacion=nit)
    assert (repetido.status_code, repetido.json()["detail"]) == (400, "Ya existe un tercero con ese tipo y número de documento.")
    sin_tipo = _crear(api, admin, numero_identificacion="123")
    assert sin_tipo.status_code == 400


def test_busqueda_por_nombre_y_documento(api, admin, vendedor):
    sufijo = uuid.uuid4().hex[:6]
    doc = _doc()
    _crear(api, admin, nombre=f"José Muñoz {sufijo}", tipo_identificacion="13", numero_identificacion=doc, cliente={})
    _crear(api, admin, nombre=f"Distribuidora Ñapa {sufijo}", proveedor={"contacto": "Ana"})
    buscar = lambda **p: [t["nombre"] for t in api.get("/terceros", headers=vendedor, params=p).json()]
    assert buscar(q=f"jose munoz {sufijo}") == [f"José Muñoz {sufijo}"]
    assert buscar(q=doc[:6], rol="cliente") == [f"José Muñoz {sufijo}"]
    assert buscar(q=sufijo, rol="proveedor") == [f"Distribuidora Ñapa {sufijo}"]
    assert "CONSUMIDOR FINAL" not in buscar(q="consumidor")


def test_cliente_y_proveedor_a_la_vez(api, admin, vendedor):
    t = _crear(api, admin, nombre=f"Carlos {uuid.uuid4().hex[:6]}", cliente={}).json()
    assert api.put(f"/terceros/{t['id']}/proveedor", headers=vendedor, json={"contacto": "x"}).status_code == 403
    r = api.put(f"/terceros/{t['id']}/proveedor", headers=admin, json={"contacto": "Carlos (celular)"})
    assert (r.json()["es_cliente"], r.json()["es_proveedor"], r.json()["contacto"]) == (True, True, "Carlos (celular)")
    assert api.put(f"/terceros/{t['id']}/proveedor", headers=admin, json={"activo": False}).json()["proveedor_activo"] is False


def test_editar_responsabilidades_y_sin_cambios(api, admin, bd):
    t = _crear(api, admin, tipo_identificacion="31", numero_identificacion=_doc()[:9], responsabilidades=["R-99-PN"]).json()
    r = api.patch(f"/terceros/{t['id']}", headers=admin, json={"responsabilidades": ["O-13", "O-15"], "telefono": "3001234567"})
    assert (r.json()["responsabilidades"], r.json()["telefono"]) == (["O-13", "O-15"], "3001234567")
    assert api.patch(f"/terceros/{t['id']}", headers=admin, json={"responsabilidades": ["X-1"]}).status_code == 400

    n = lambda: bd.execute("SELECT count(*) AS n FROM auditoria WHERE entidad_id = %s", (t["id"],)).fetchone()["n"]
    antes = n()
    api.patch(f"/terceros/{t['id']}", headers=admin, json={"telefono": "3001234567", "responsabilidades": ["O-15", "O-13"]})
    assert n() == antes
    # Borrar un dato opcional con null.
    assert api.patch(f"/terceros/{t['id']}", headers=admin, json={"telefono": None}).json()["telefono"] is None


def test_consumidor_final_y_negocio_no_se_editan(api, admin, bd):
    cf = bd.execute("SELECT id FROM terceros WHERE nombre = 'CONSUMIDOR FINAL'").fetchone()["id"]
    r = api.patch(f"/terceros/{cf}", headers=admin, json={"nombre": "Otro"})
    assert r.status_code == 400 and "no se usa aquí" in r.json()["detail"]
    assert api.put(f"/terceros/{cf}/cliente", headers=admin, json={}).status_code == 400


def test_vincular_usuario_con_su_persona(api, admin, crear_usuario):
    uid, _ = crear_usuario()
    persona = _crear(api, admin, nombre=f"Laura {uuid.uuid4().hex[:6]}", cliente={}).json()
    r = api.patch(f"/usuarios/{uid}", headers=admin, json={"tercero_id": persona["id"]})
    assert r.status_code == 200 and r.json()["tercero_id"] == persona["id"]
    assert api.get(f"/terceros/{persona['id']}", headers=admin).json()["usuario_id"] == str(uid)

    otro, _ = crear_usuario()
    doble = api.patch(f"/usuarios/{otro}", headers=admin, json={"tercero_id": persona["id"]})
    assert (doble.status_code, doble.json()["detail"]) == (400, "Esa persona ya tiene un usuario.")
    assert api.patch(f"/usuarios/{uid}", headers=admin, json={"tercero_id": None}).json()["tercero_id"] is None


def test_buscar_documento_escrito_con_formato(api, admin, vendedor):
    from pos_api.servicios.comun import digito_verificacion
    nit = _doc()[:9]
    _crear(api, admin, nombre=f"Proveedor {nit}", tipo_identificacion="31", numero_identificacion=nit)
    formateado = f"{nit[:3]}.{nit[3:6]}.{nit[6:]}-{digito_verificacion(nit)}"
    assert [x["numero_identificacion"] for x in api.get("/terceros", headers=vendedor, params={"q": formateado}).json()] == [nit]


def test_editar_es_todo_o_nada(api, admin, vendedor, bd):
    t = _crear(api, admin, nombre=f"Ana {uuid.uuid4().hex[:6]}", cliente={}).json()
    # El nombre se cambiaría, pero el cupo no lo puede tocar el cajero: no queda nada.
    r = api.patch(f"/terceros/{t['id']}", headers=vendedor, json={"nombre": "Otro nombre", "cliente": {"limite_credito": "90000"}})
    assert r.status_code == 403
    assert api.get(f"/terceros/{t['id']}", headers=admin).json()["nombre"] == t["nombre"]
    r = api.patch(f"/terceros/{t['id']}", headers=admin, json={"nombre": "Ana B", "cliente": {"limite_credito": "90000"}})
    assert (r.json()["nombre"], r.json()["limite_credito"]) == ("Ana B", 90000)


def test_quitar_el_documento(api, admin):
    t = _crear(api, admin, tipo_identificacion="13", numero_identificacion=_doc()).json()
    r = api.patch(f"/terceros/{t['id']}", headers=admin, json={"tipo_identificacion": None, "numero_identificacion": None})
    assert (r.status_code, r.json()["tipo_identificacion"], r.json()["numero_identificacion"]) == (200, None, None)


def test_proveedor_nuevo_queda_en_auditoria_de_compras(api, admin, bd):
    t = _crear(api, admin, nombre=f"Prov {uuid.uuid4().hex[:6]}", proveedor={}).json()
    acciones = {r["accion"] for r in bd.execute("SELECT accion FROM auditoria WHERE entidad_id = %s", (t["id"],))}
    assert acciones == {"compra"}


def test_no_se_vincula_un_usuario_a_consumidor_final(api, admin, crear_usuario, bd):
    uid, _ = crear_usuario()
    cf = bd.execute("SELECT id FROM terceros WHERE es_consumidor_final").fetchone()["id"]
    r = api.patch(f"/usuarios/{uid}", headers=admin, json={"tercero_id": str(cf)})
    assert r.status_code == 400 and "CONSUMIDOR FINAL" in r.json()["detail"]
