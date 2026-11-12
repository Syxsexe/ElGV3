"""
pos_api/pruebas/conftest.py — Pruebas de la API contra un Postgres real.

Igual que db/pruebas: necesitan PRUEBAS_DATABASE_URL (db/pg_local.sh) y las
dependencias de pos_api; si falta algo, se saltan. Cada sesión crea una base
desechable con todas las migraciones y la borra al final.

Los endpoints confirman sus propias transacciones, así que las pruebas no se
revierten: cada una arma sus datos con nombres únicos (Fabrica) y no depende
de lo que hayan dejado las demás.
"""
import os
import uuid

import pytest

URL = os.environ.get("PRUEBAS_DATABASE_URL")
try:
    import argon2  # noqa: F401
    import fastapi  # noqa: F401
    import jwt  # noqa: F401
    import psycopg
    import psycopg_pool  # noqa: F401
except ImportError:
    psycopg = None

if (not URL or psycopg is None) and os.environ.get("PRUEBAS_EXIGIR"):
    # En CI faltar la base o una dependencia es un error, no un salto.
    raise RuntimeError("PRUEBAS_EXIGIR: faltan PRUEBAS_DATABASE_URL o dependencias para las pruebas de la API.")
if not URL or psycopg is None:
    collect_ignore_glob = ["test_*.py"]
else:
    from fastapi.testclient import TestClient
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg.rows import dict_row

    from db import migrar
    from db.pruebas.ayudas import Fabrica
    from pos_api import main
    from pos_api.seguridad import hash_contrasena

    CONTRASENA = "clave-de-prueba"

    @pytest.fixture(scope="session")
    def url_prueba():
        nombre = f"elg_prueba_api_{uuid.uuid4().hex[:10]}"
        with psycopg.connect(URL, autocommit=True) as admin:
            admin.execute(f'CREATE DATABASE "{nombre}"')
        url = make_conninfo(**{**conninfo_to_dict(URL), "dbname": nombre})
        try:
            migrar.aplicar(url, verbose=False)
            yield url
        finally:
            with psycopg.connect(URL, autocommit=True) as admin:
                admin.execute(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)')

    @pytest.fixture(scope="session")
    def api(url_prueba):
        """Cliente HTTP de la app, con su pool apuntando a la base de prueba."""
        original = main.DATABASE_URL
        main.DATABASE_URL = url_prueba
        try:
            with TestClient(main.app) as cliente:
                yield cliente
        finally:
            main.DATABASE_URL = original

    @pytest.fixture
    def bd(url_prueba):
        """Conexión en autocommit para preparar datos: lo que va junto (un
        artículo y su subtipo) se agrupa en `with bd.transaction():`."""
        with psycopg.connect(url_prueba, autocommit=True, row_factory=dict_row) as conn:
            yield conn

    @pytest.fixture
    def f(bd):
        return Fabrica(bd)

    @pytest.fixture
    def turno(bd, f):
        """El turno abierto (solo puede haber uno en toda la base de prueba):
        lo reutiliza si otra prueba ya lo abrió, con sus cajas Efectivo y Digital."""
        fila = bd.execute("SELECT id FROM sesiones_caja WHERE cerrada_en IS NULL").fetchone()
        return fila["id"] if fila else f.turno()

    @pytest.fixture
    def crear_usuario(bd):
        """crear_usuario(rol="vendedor") → (id, nombre) con contraseña CONTRASENA."""
        def _crear(rol="vendedor", activo=True):
            nombre = f"u-{uuid.uuid4().hex[:8]}"
            fila = bd.execute(
                "INSERT INTO usuarios (usuario, contrasena_hash, rol_id, activo) "
                "SELECT %s, %s, id, %s FROM roles WHERE nombre = %s RETURNING id",
                (nombre, hash_contrasena(CONTRASENA), activo, rol)).fetchone()
            return fila["id"], nombre
        return _crear

    @pytest.fixture
    def sesion(api, crear_usuario):
        """sesion(rol) → headers con el token de un usuario nuevo de ese rol."""
        def _sesion(rol="vendedor"):
            _, nombre = crear_usuario(rol)
            r = api.post("/auth/login", json={"usuario": nombre, "contrasena": CONTRASENA})
            assert r.status_code == 200, r.text
            return {"Authorization": f"Bearer {r.json()['token']}"}
        return _sesion

    @pytest.fixture
    def base_nueva():
        """URL de una base recién migrada, sin usuarios (para la configuración inicial)."""
        nombre = f"elg_prueba_nueva_{uuid.uuid4().hex[:10]}"
        with psycopg.connect(URL, autocommit=True) as admin:
            admin.execute(f'CREATE DATABASE "{nombre}"')
        url = make_conninfo(**{**conninfo_to_dict(URL), "dbname": nombre})
        try:
            yield url
        finally:
            with psycopg.connect(URL, autocommit=True) as admin:
                admin.execute(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)')
