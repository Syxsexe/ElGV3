"""Bitácora de auditoría (auditoria.ver)."""
import datetime as dt


def test_lista_filtra_y_pagina(api, sesion, crear_usuario):
    h = sesion("admin")
    uid, nombre = crear_usuario()
    for _ in range(3):
        api.post("/auth/login", json={"usuario": nombre, "contrasena": "clave-de-prueba"})

    eventos = api.get("/auditoria", headers=h, params={"usuario_id": str(uid), "accion": "login"}).json()
    assert len(eventos) == 3 and all(e["usuario"] == nombre for e in eventos)
    pagina = api.get("/auditoria", headers=h, params={"usuario_id": str(uid), "limite": 2}).json()
    resto = api.get("/auditoria", headers=h, params={"usuario_id": str(uid), "antes": pagina[-1]["id"]}).json()
    assert len(pagina) == 2 and len(resto) == 1 and resto[0]["id"] not in {e["id"] for e in pagina}

    hoy = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5))).date()
    assert len(api.get("/auditoria", headers=h, params={"usuario_id": str(uid), "desde": str(hoy), "hasta": str(hoy)}).json()) == 3
    assert api.get("/auditoria", headers=h, params={"usuario_id": str(uid), "hasta": str(hoy - dt.timedelta(days=1))}).json() == []


def test_vendedor_no_ve_auditoria(api, sesion):
    assert api.get("/auditoria", headers=sesion("vendedor")).status_code == 403
