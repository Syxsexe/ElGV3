"""Usuarios, roles y permisos (usuarios.gestionar)."""
import time
import uuid

import pytest

from pos_api.pruebas.conftest import CONTRASENA


def _rol(api, h, nombre):
    return next(r for r in api.get("/roles", headers=h).json() if r["nombre"] == nombre)


def test_solo_quien_gestiona_usuarios_entra(api, sesion):
    vendedor = sesion("vendedor")
    for metodo, ruta in (("get", "/usuarios"), ("get", "/roles"), ("post", "/usuarios"), ("delete", f"/roles/{uuid.uuid4()}")):
        assert getattr(api, metodo)(ruta, headers=vendedor).status_code == 403


def test_crear_usuario_y_entrar_con_el(api, sesion, bd):
    h = sesion("admin")
    vendedor_id = _rol(api, h, "vendedor")["id"]
    nombre = f"cajero-{uuid.uuid4().hex[:6]}"
    r = api.post("/usuarios", headers=h, json={"usuario": f"  {nombre} ", "contrasena": "clave-segura", "rol_id": vendedor_id})
    assert r.status_code == 201 and r.json()["usuario"] == nombre
    assert api.post("/auth/login", json={"usuario": nombre, "contrasena": "clave-segura"}).status_code == 200

    repetido = api.post("/usuarios", headers=h, json={"usuario": nombre, "contrasena": "clave-segura", "rol_id": vendedor_id})
    assert (repetido.status_code, repetido.json()["detail"]) == (400, "Ya existe un usuario con ese nombre.")
    corta = api.post("/usuarios", headers=h, json={"usuario": "otro-" + nombre, "contrasena": "corta", "rol_id": vendedor_id})
    assert corta.status_code == 400 and "al menos 8" in corta.json()["detail"]
    assert bd.execute("SELECT count(*) AS n FROM auditoria WHERE entidad_id = %s", (r.json()["id"],)).fetchone()["n"] == 1


def test_desactivar_y_restablecer_contrasena(api, sesion, crear_usuario):
    h = sesion("admin")
    uid, nombre = crear_usuario()
    assert api.patch(f"/usuarios/{uid}", headers=h, json={"activo": False}).json()["activo"] is False
    assert api.post("/auth/login", json={"usuario": nombre, "contrasena": CONTRASENA}).status_code == 401
    api.patch(f"/usuarios/{uid}", headers=h, json={"activo": True})
    token_viejo = api.post("/auth/login", json={"usuario": nombre, "contrasena": CONTRASENA}).json()["token"]
    time.sleep(1)
    assert api.post(f"/usuarios/{uid}/contrasena", headers=h, json={"contrasena": "otra-clave-1"}).status_code == 200
    assert api.get("/auth/yo", headers={"Authorization": f"Bearer {token_viejo}"}).status_code == 401
    assert api.post("/auth/login", json={"usuario": nombre, "contrasena": "otra-clave-1"}).status_code == 200
    assert api.patch(f"/usuarios/{uuid.uuid4()}", headers=h, json={"activo": False}).status_code == 404


def test_cambiar_mi_contrasena(api, crear_usuario):
    _, nombre = crear_usuario()
    token = api.post("/auth/login", json={"usuario": nombre, "contrasena": CONTRASENA}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    mala = api.post("/auth/contrasena", headers=h, json={"actual": "no-es", "nueva": "nueva-clave-1"})
    assert (mala.status_code, mala.json()["detail"]) == (400, "La contraseña actual no es correcta.")
    time.sleep(1)  # el iat del token va en segundos
    r = api.post("/auth/contrasena", headers=h, json={"actual": CONTRASENA, "nueva": "nueva-clave-1"})
    assert r.status_code == 200
    # El token viejo (otra sesión) ya no vale; el nuevo sí.
    assert api.get("/auth/yo", headers=h).status_code == 401
    assert api.get("/auth/yo", headers={"Authorization": f"Bearer {r.json()['token']}"}).status_code == 200
    assert api.post("/auth/login", json={"usuario": nombre, "contrasena": "nueva-clave-1"}).status_code == 200


def test_roles_con_permisos(api, sesion, crear_usuario, bd):
    h = sesion("admin")
    nombre = f"Bodega {uuid.uuid4().hex[:6]}"
    r = api.post("/roles", headers=h, json={"nombre": nombre, "permisos": ["inventario.editar", "combos.editar"]})
    assert r.status_code == 201
    rol_id = r.json()["id"]
    assert _rol(api, h, nombre)["permisos"] == ["combos.editar", "inventario.editar"]

    assert api.patch(f"/roles/{rol_id}", headers=h, json={"permisos": ["reportes.ver"]}).status_code == 200
    assert _rol(api, h, nombre)["permisos"] == ["reportes.ver"]
    malo = api.patch(f"/roles/{rol_id}", headers=h, json={"permisos": ["no.existe"]})
    assert (malo.status_code, malo.json()["detail"]) == (400, "Permisos desconocidos: no.existe.")

    # Con usuarios no se borra; sin usuarios sí.
    uid, _ = crear_usuario()
    bd.execute("UPDATE usuarios SET rol_id = %s WHERE id = %s", (rol_id, uid))
    assert api.delete(f"/roles/{rol_id}", headers=h).status_code == 400
    bd.execute("UPDATE usuarios SET rol_id = (SELECT id FROM roles WHERE nombre = 'vendedor') WHERE id = %s", (uid,))
    assert api.delete(f"/roles/{rol_id}", headers=h).status_code == 200


def test_rol_admin_no_se_toca(api, sesion):
    h = sesion("admin")
    admin_id = _rol(api, h, "admin")["id"]
    for r in (api.patch(f"/roles/{admin_id}", headers=h, json={"permisos": []}),
              api.delete(f"/roles/{admin_id}", headers=h)):
        assert r.status_code == 400 and "rol admin" in r.json()["detail"]


@pytest.fixture
def unico_gestor(bd, crear_usuario):
    """Deja un solo usuario activo con usuarios.gestionar (los demás se
    desactivan durante la prueba y se reactivan al final)."""
    uid, nombre = crear_usuario("admin")
    otros = [r["id"] for r in bd.execute(
        "UPDATE usuarios SET activo = false WHERE activo AND id <> %s RETURNING id", (uid,))]
    yield uid, nombre
    bd.execute("UPDATE usuarios SET activo = true WHERE id = ANY (%s)", (otros,))


def test_siempre_queda_alguien_que_gestione_usuarios(api, unico_gestor, bd):
    uid, nombre = unico_gestor
    token = api.post("/auth/login", json={"usuario": nombre, "contrasena": CONTRASENA}).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    vendedor_id = _rol(api, h, "vendedor")["id"]
    for cambio in ({"activo": False}, {"rol_id": vendedor_id}):
        r = api.patch(f"/usuarios/{uid}", headers=h, json=cambio)
        assert r.status_code == 400 and "al menos un usuario activo" in r.json()["detail"]
    assert bd.execute("SELECT activo FROM usuarios WHERE id = %s", (uid,)).fetchone()["activo"] is True


def test_quien_gestiona_usuarios_no_da_mas_de_lo_que_tiene(api, sesion, crear_usuario, bd):
    admin = sesion("admin")
    nombre = f"Supervisor {uuid.uuid4().hex[:6]}"
    rol_id = api.post("/roles", headers=admin, json={"nombre": nombre, "permisos": ["usuarios.gestionar"]}).json()["id"]
    sup_id, sup = crear_usuario()
    bd.execute("UPDATE usuarios SET rol_id = %s WHERE id = %s", (rol_id, sup_id))
    h = {"Authorization": f"Bearer {api.post('/auth/login', json={'usuario': sup, 'contrasena': CONTRASENA}).json()['token']}"}
    roles = {r["nombre"]: r["id"] for r in api.get("/roles", headers=h).json()}
    admin_id, _ = crear_usuario("admin")

    # Puede crear cajeros (vendedor no tiene permisos)…
    assert api.post("/usuarios", headers=h, json={"usuario": f"caj-{uuid.uuid4().hex[:6]}", "contrasena": "clave-segura",
                                                  "rol_id": roles["vendedor"]}).status_code == 201
    # …pero no volverse admin, ni tocar a un admin, ni armar roles con permisos que no tiene.
    intentos = [
        api.patch(f"/usuarios/{sup_id}", headers=h, json={"rol_id": roles["admin"]}),
        api.post(f"/usuarios/{admin_id}/contrasena", headers=h, json={"contrasena": "me-adueno-1"}),
        api.patch(f"/usuarios/{admin_id}", headers=h, json={"activo": False}),
        api.post("/roles", headers=h, json={"nombre": nombre + " 2", "permisos": ["reportes.ver"]}),
        api.patch(f"/roles/{rol_id}", headers=h, json={"permisos": ["usuarios.gestionar", "auditoria.ver"]}),
    ]
    for r in intentos:
        assert r.status_code == 403, r.text
        assert "permisos que tú no tienes" in r.json()["detail"]


def test_editar_sin_cambios_no_audita(api, sesion, crear_usuario, bd):
    h = sesion("admin")
    uid, _ = crear_usuario()
    rol = bd.execute("SELECT rol_id FROM usuarios WHERE id = %s", (uid,)).fetchone()["rol_id"]
    api.patch(f"/usuarios/{uid}", headers=h, json={"rol_id": str(rol), "activo": True})
    assert bd.execute("SELECT count(*) AS n FROM auditoria WHERE entidad_id = %s", (uid,)).fetchone()["n"] == 0
    api.patch(f"/usuarios/{uid}", headers=h, json={"activo": False})
    assert bd.execute("SELECT detalle FROM auditoria WHERE entidad_id = %s", (uid,)).fetchone()["detalle"].endswith("desactivado")


def test_dos_gestores_que_se_desactivan_a_la_vez(base_nueva):
    # Con el candado, el segundo espera al primero y luego ve que ya no queda nadie.
    import psycopg
    from psycopg.rows import dict_row

    from db import migrar
    from pos_api.errores import ErrorNegocio
    from pos_api.seguridad import cargar_usuario
    from pos_api.servicios.usuarios import editar_usuario

    migrar.aplicar(base_nueva, verbose=False)
    with psycopg.connect(base_nueva, autocommit=True, row_factory=dict_row) as base:
        ids = [base.execute("INSERT INTO usuarios (usuario, contrasena_hash, rol_id) "
                            "SELECT %s, 'x', id FROM roles WHERE nombre = 'admin' RETURNING id", (n,)).fetchone()["id"]
               for n in ("a", "b")]
        a, b = (cargar_usuario(base, i) for i in ids)
    con_a = psycopg.connect(base_nueva, row_factory=dict_row)
    con_b = psycopg.connect(base_nueva, row_factory=dict_row)
    try:
        editar_usuario(con_a, a, b.id, {"activo": False})
        con_b.execute("SET lock_timeout = '300ms'")
        with pytest.raises(psycopg.errors.LockNotAvailable):
            editar_usuario(con_b, b, a.id, {"activo": False})
        con_b.rollback()
        con_a.commit()
        with pytest.raises(ErrorNegocio, match="al menos un usuario activo"):
            editar_usuario(con_b, b, a.id, {"activo": False})
    finally:
        con_a.close()
        con_b.close()
