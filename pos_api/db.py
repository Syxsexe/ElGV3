"""
pos_api/db.py — Conexiones a Postgres.

Un pool por proceso, abierto en el lifespan de la app. Cada endpoint abre su
transacción con `transaccion()` y la cierra antes de responder: los cuadres
son triggers diferidos que se revisan al confirmar, así que un error de cuadre
sale dentro del endpoint y se convierte en un 400 con su mensaje.
"""
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from db.migrar import migraciones_disponibles
from pos_api.config import ZONA_HORARIA

# Si un cierre de turno tiene bloqueado el turno, una venta espera hasta esto y
# luego falla con LockNotAvailable (503 "intenta de nuevo") en vez de colgarse.
LOCK_TIMEOUT_MS = 5000

_pool: ConnectionPool | None = None


def abrir_pool(url: str) -> None:
    global _pool
    _pool = ConnectionPool(
        url,
        min_size=1,
        max_size=10,
        kwargs={
            "row_factory": dict_row,
            "options": f"-c lock_timeout={LOCK_TIMEOUT_MS} -c TimeZone={ZONA_HORARIA}",
        },
        # Verifica cada conexión antes de entregarla: si Postgres se reinició,
        # la conexión muerta se reemplaza en vez de fallar el request.
        check=ConnectionPool.check_connection,
        open=True,
    )


def cerrar_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def transaccion():
    """Conexión del pool dentro de una transacción: confirma al salir del
    bloque (ahí se revisan los triggers diferidos) o revierte si hubo error."""
    if _pool is None:
        raise RuntimeError("El pool de conexiones no está abierto.")
    with _pool.connection() as conn:
        with conn.transaction():
            yield conn


def migraciones_pendientes(url: str) -> list[str]:
    """Versiones de db/migraciones que la base todavía no tiene."""
    with psycopg.connect(url) as conn:
        existe = conn.execute("SELECT to_regclass('schema_migraciones') IS NOT NULL").fetchone()[0]
        hechas = {r[0] for r in conn.execute("SELECT version FROM schema_migraciones")} if existe else set()
    return [a.stem for a in migraciones_disponibles() if a.stem not in hechas]
