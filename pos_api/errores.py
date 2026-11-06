"""
pos_api/errores.py — Errores del negocio y de Postgres → respuestas HTTP.

Las reglas viven en la base: la API inserta y deja que Postgres rechace. Los
triggers ya lanzan mensajes en español pensados para el usuario, así que se
devuelven tal cual. Las restricciones con nombre (UNIQUE, CHECK) se traducen
con MENSAJES; las que falten ahí salen con un mensaje genérico.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import psycopg
from psycopg import errors as pg

log = logging.getLogger(__name__)


class ErrorNegocio(Exception):
    """Regla que valida la API (no la base). Sale como 400 con su mensaje."""


class NoEncontrado(Exception):
    """El registro pedido no existe. Sale como 404 con su mensaje."""


MENSAJES = {
    "sesiones_caja_un_turno_abierto": "Ya hay un turno de caja abierto.",
    "cuentas_una_abierta_por_mesa": "Esa mesa ya tiene una cuenta abierta.",
    "usuarios_usuario_key": "Ya existe un usuario con ese nombre.",
    "usuarios_tercero_id_key": "Esa persona ya tiene un usuario.",
    "terceros_identificacion_unica": "Ya existe un tercero con ese tipo y número de documento.",
    "empresa_pkey": "Los datos del negocio ya están configurados.",
}

# Errores de regla (400): el dato no es válido y reintentar igual no sirve.
# Integridad (clase 23: CHECK, UNIQUE, FK, NOT NULL, y los RAISE de triggers
# con esos códigos), datos mal formados o fuera de rango (clase 22) y los RAISE
# sin código (P0001).
_REGLA = (psycopg.IntegrityError, psycopg.DataError, pg.RaiseException)
# Errores de disponibilidad (503): bloqueos, conflictos de concurrencia, pool
# agotado o base caída (OperationalError, que incluye PoolTimeout); reintentar sí sirve.
_OCUPADA = (psycopg.OperationalError,)


def mensaje_de(exc: pg.Error) -> str:
    diag = exc.diag
    restriccion = diag.constraint_name
    if restriccion in MENSAJES:
        return MENSAJES[restriccion]
    if isinstance(exc, pg.ForeignKeyViolation):
        if "still referenced" in (diag.message_detail or ""):
            return "No se puede borrar: otros registros dependen de este."
        return "Uno de los registros indicados no existe."
    if isinstance(exc, pg.UniqueViolation):
        return "Ya existe un registro con esos datos."
    if isinstance(exc, pg.NotNullViolation):
        return f"Falta un dato obligatorio ({diag.column_name})."
    if isinstance(exc, psycopg.DataError):
        return "Uno de los datos tiene un formato inválido o está fuera de rango."
    if restriccion:
        # CHECK de la tabla (el mensaje de Postgres viene en inglés y con SQL).
        return f"Datos inválidos (regla {restriccion})."
    # RAISE de un trigger: ya es un mensaje para el usuario.
    return diag.message_primary or "Operación inválida."


def registrar(app: FastAPI) -> None:
    @app.exception_handler(ErrorNegocio)
    def _negocio(request: Request, exc: ErrorNegocio):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(NoEncontrado)
    def _no_encontrado(request: Request, exc: NoEncontrado):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(pg.Error)
    def _postgres(request: Request, exc: pg.Error):
        if isinstance(exc, _REGLA):
            return JSONResponse(status_code=400, content={"detail": mensaje_de(exc)})
        if isinstance(exc, _OCUPADA):
            log.warning("Base de datos no disponible: %s", exc)
            return JSONResponse(status_code=503, content={"detail": "La base de datos está ocupada, intenta de nuevo."})
        log.exception("Error de base de datos no esperado")
        return JSONResponse(status_code=500, content={"detail": "Error interno de la base de datos."})
