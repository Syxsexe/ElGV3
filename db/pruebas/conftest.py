"""
db/pruebas/conftest.py — Pruebas del esquema Postgres contra una base real.

Necesitan PRUEBAS_DATABASE_URL apuntando a un servidor Postgres 18
(db/pg_local.sh) y psycopg instalado (db/requirements.txt); si falta algo, se
saltan. No usan DATABASE_URL porque las pruebas del backend la redefinen. Cada sesión
crea una base desechable, le aplica todas las migraciones y la borra al final.
Cada prueba corre en una transacción que se revierte, así que no se ven entre sí.
"""
import os
import sys
import uuid
from pathlib import Path

import pytest

URL = os.environ.get("PRUEBAS_DATABASE_URL")
try:
    import psycopg
except ImportError:
    psycopg = None

if (not URL or psycopg is None) and os.environ.get("PRUEBAS_EXIGIR"):
    # En CI faltar la base o una dependencia es un error, no un salto.
    raise RuntimeError("PRUEBAS_EXIGIR: faltan PRUEBAS_DATABASE_URL o dependencias para las pruebas de la base.")
if not URL or psycopg is None:
    # Sin Postgres no hay nada que probar aquí: no se recolectan estas pruebas.
    collect_ignore_glob = ["test_*.py"]
else:
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg.rows import dict_row

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import migrar
    from ayudas import Fabrica

    @pytest.fixture(scope="session")
    def url_prueba():
        nombre = f"elg_prueba_{uuid.uuid4().hex[:10]}"
        with psycopg.connect(URL, autocommit=True) as admin:
            admin.execute(f'CREATE DATABASE "{nombre}"')
        url = make_conninfo(**{**conninfo_to_dict(URL), "dbname": nombre})
        try:
            migrar.aplicar(url, verbose=False)
            yield url
        finally:
            with psycopg.connect(URL, autocommit=True) as admin:
                admin.execute(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)')


    @pytest.fixture
    def db(url_prueba):
        conn = psycopg.connect(url_prueba, row_factory=dict_row)
        try:
            yield conn
        finally:
            conn.rollback()
            conn.close()


    @pytest.fixture
    def f(db):
        return Fabrica(db)
