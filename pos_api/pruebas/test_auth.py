"""Login, sesión por token y permisos."""
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from pos_api.pruebas.conftest import CONTRASENA
from pos_api.seguridad import requiere_permiso


def _login(api, usuario, contrasena=CONTRASENA):
    return api.post("/auth/login", json={"usuario": usuario, "contrasena": contrasena})


def test_login_correcto_devuelve_token_y_permisos(api, crear_usuario, bd):
    uid, nombre = crear_usuario("admin")
    r = _login(api, nombre)
    assert r.status_code == 200
    datos = r.json()
    assert datos["usuario"] == nombre and datos["rol"] == "admin"
    assert "caja.historial" in datos["permisos"] and "reportes.ver" in datos["permisos"]
    assert bd.execute("SELECT count(*) AS n FROM auditoria WHERE usuario_id = %s AND accion = 'login'",
                      (uid,)).fetchone()["n"] == 1


def test_contrasena_mala_usuario_inexistente_o_inactivo_dan_401(api, crear_usuario):
    _, activo = crear_usuario()
    _, inactivo = crear_usuario(activo=False)
    for usuario, clave in ((activo, "otra-clave"), ("no-existe", CONTRASENA), (inactivo, CONTRASENA)):
        r = _login(api, usuario, clave)
        assert r.status_code == 401
        assert r.json()["detail"] == "Usuario o contraseña incorrectos."


def test_yo_lee_el_usuario_en_cada_request(api, crear_usuario, bd):
    uid, nombre = crear_usuario("vendedor")
    headers = {"Authorization": f"Bearer {_login(api, nombre).json()['token']}"}
    yo = api.get("/auth/yo", headers=headers).json()
    assert (yo["usuario"], yo["rol"], yo["permisos"]) == (nombre, "vendedor", [])

    # Cambiar el rol aplica sin volver a iniciar sesión…
    bd.execute("UPDATE usuarios SET rol_id = (SELECT id FROM roles WHERE nombre = 'admin') WHERE id = %s", (uid,))
    assert api.get("/auth/yo", headers=headers).json()["rol"] == "admin"
    # …y desactivarlo corta la sesión de inmediato.
    bd.execute("UPDATE usuarios SET activo = false WHERE id = %s", (uid,))
    assert api.get("/auth/yo", headers=headers).status_code == 401


def test_sin_token_o_token_falso_da_401(api):
    assert api.get("/auth/yo").status_code == 401
    assert api.get("/auth/yo", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_requiere_permiso(api, sesion):
    # Una ruta de prueba aparte (sin tocar la app real) que exige un permiso.
    app = FastAPI()

    @app.get("/protegida")
    def protegida(usuario=Depends(requiere_permiso("caja.historial"))):
        return {"ok": usuario.usuario}

    prueba = TestClient(app)
    assert prueba.get("/protegida", headers=sesion("vendedor")).status_code == 403
    assert prueba.get("/protegida", headers=sesion("admin")).status_code == 200
