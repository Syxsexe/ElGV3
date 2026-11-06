"""Configuración inicial (python -m pos_api.configurar) y chequeo de migraciones."""
import psycopg
import pytest
from psycopg.rows import dict_row

from db import migrar
from pos_api.configurar import crear_configuracion, digito_verificacion
from pos_api.db import migraciones_pendientes
from pos_api.errores import ErrorNegocio
from pos_api.seguridad import verificar_credenciales

NEGOCIO = {
    "tipo_identificacion": "31", "numero_identificacion": "900123456", "nombre": "El G SAS",
    "tipo_persona": "juridica", "direccion": "Calle 1", "telefono": None, "email": None,
    "responsable_iva": False, "regimen_tributario": "simple", "responsable_inc": False,
}


def test_digito_de_verificacion():
    assert digito_verificacion("800197268") == 4  # NIT de la DIAN
    assert digito_verificacion("900123456") == 8
    with pytest.raises(ValueError):
        digito_verificacion("90012345-6")


def test_base_sin_migrar_tiene_todo_pendiente(base_nueva):
    pendientes = migraciones_pendientes(base_nueva)
    assert pendientes[0] == "0001_terceros" and pendientes[-1] == "0015_fase3"
    migrar.aplicar(base_nueva, verbose=False)
    assert migraciones_pendientes(base_nueva) == []


def test_crea_negocio_y_admin_una_sola_vez(base_nueva):
    migrar.aplicar(base_nueva, verbose=False)
    with psycopg.connect(base_nueva, row_factory=dict_row) as conn:
        municipio = conn.execute("SELECT id FROM municipios WHERE codigo = '52001'").fetchone()["id"]
        with conn.transaction():
            crear_configuracion(conn, {**NEGOCIO, "municipio_id": municipio},
                                {"usuario": " admin ", "contrasena": "una-clave-larga"})

        empresa = conn.execute("""
            SELECT t.nombre, t.numero_identificacion, e.regimen_tributario
              FROM empresa e JOIN terceros t ON t.id = e.tercero_id""").fetchone()
        assert empresa == {"nombre": "El G SAS", "numero_identificacion": "900123456", "regimen_tributario": "simple"}
        with conn.transaction():
            admin = verificar_credenciales(conn, "admin", "una-clave-larga")
        assert admin.rol == "admin" and admin.puede("usuarios.gestionar")
        assert conn.execute("SELECT count(*) AS n FROM auditoria WHERE usuario_id IS NULL").fetchone()["n"] == 2

        with pytest.raises(ErrorNegocio, match="ya está configurada"):
            with conn.transaction():
                crear_configuracion(conn, {**NEGOCIO, "municipio_id": municipio},
                                    {"usuario": "otro", "contrasena": "una-clave-larga"})


def test_contrasena_corta_no_crea_nada(base_nueva):
    migrar.aplicar(base_nueva, verbose=False)
    with psycopg.connect(base_nueva, row_factory=dict_row) as conn:
        with pytest.raises(ErrorNegocio, match="al menos 8"):
            with conn.transaction():
                crear_configuracion(conn, {**NEGOCIO, "municipio_id": None},
                                    {"usuario": "admin", "contrasena": "corta"})
        assert conn.execute("SELECT count(*) AS n FROM empresa").fetchone()["n"] == 0
