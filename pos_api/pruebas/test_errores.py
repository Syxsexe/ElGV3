"""Errores de Postgres → respuestas HTTP con mensajes para el usuario."""
import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout

from pos_api import errores
from pos_api.db import transaccion


@pytest.fixture
def ejecutar(api):
    """ejecutar(sql) corre el SQL en un endpoint de prueba y devuelve la respuesta."""
    app = FastAPI()
    errores.registrar(app)

    @app.post("/sql")
    def sql(cuerpo: dict):
        with transaccion() as conn:
            for sentencia in cuerpo["sql"]:
                conn.execute(sentencia)
        return {"ok": True}

    @app.get("/pool-agotado")
    def pool_agotado():
        raise PoolTimeout("couldn't get a connection after 30.00 sec")

    cliente = TestClient(app, raise_server_exceptions=False)

    def ejecutar(*sentencias):
        return cliente.post("/sql", json={"sql": list(sentencias)})
    ejecutar.cliente = cliente
    return ejecutar


def test_mensaje_de_un_trigger_sale_tal_cual(ejecutar):
    r = ejecutar("DELETE FROM auditoria")
    assert r.status_code == 400
    assert r.json()["detail"] == "auditoria es de solo inserción: no se permite DELETE"


def test_restriccion_con_nombre_conocido_se_traduce(ejecutar):
    r = ejecutar("INSERT INTO usuarios (usuario, contrasena_hash, rol_id) "
                 "SELECT 'repetido', 'x', id FROM roles WHERE nombre = 'admin'",
                 "INSERT INTO usuarios (usuario, contrasena_hash, rol_id) "
                 "SELECT 'repetido', 'x', id FROM roles WHERE nombre = 'admin'")
    assert (r.status_code, r.json()["detail"]) == (400, "Ya existe un usuario con ese nombre.")


def test_check_y_fk_salen_con_mensaje_generico(ejecutar):
    r = ejecutar("INSERT INTO categorias (nombre, tipo) VALUES ('X', 'otra')")
    assert (r.status_code, r.json()["detail"]) == (400, "Datos inválidos (regla categorias_tipo_check).")
    r = ejecutar("INSERT INTO municipios (codigo, nombre, departamento_id) VALUES ('99999', 'X', uuidv7())")
    assert (r.status_code, r.json()["detail"]) == (400, "Uno de los registros indicados no existe.")


def test_cuadre_diferido_falla_dentro_del_endpoint(ejecutar, f):
    s = f.turno()
    r = ejecutar(f"INSERT INTO ventas (sesion_id, usuario_id) VALUES ('{s}', (SELECT abierta_por FROM sesiones_caja WHERE id = '{s}'))")
    assert r.status_code == 400
    assert r.json()["detail"].endswith("no tiene líneas")


def test_error_inesperado_es_500_sin_sql(ejecutar):
    r = ejecutar("SELECT * FROM tabla_que_no_existe")
    assert r.status_code == 500
    assert r.json()["detail"] == "Error interno de la base de datos."


def test_mensaje_de_unique_sin_traduccion():
    exc = psycopg.errors.UniqueViolation()
    assert errores.mensaje_de(exc) == "Ya existe un registro con esos datos."


def test_dato_fuera_de_rango_es_400(ejecutar):
    r = ejecutar("SELECT 99999999999999999::numeric(14,2)")
    assert (r.status_code, r.json()["detail"]) == (
        400, "Uno de los datos tiene un formato inválido o está fuera de rango.")


def test_pool_agotado_es_503(ejecutar):
    r = ejecutar.cliente.get("/pool-agotado")
    assert (r.status_code, r.json()["detail"]) == (503, "La base de datos está ocupada, intenta de nuevo.")
