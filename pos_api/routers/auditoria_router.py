"""pos_api/routers/auditoria_router.py — bitácora de acciones (auditoria.ver)."""
import datetime as dt
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query

from pos_api.auditoria import listar_auditoria
from pos_api.db import transaccion
from pos_api.seguridad import Usuario, requiere_permiso

router = APIRouter(prefix="/auditoria", tags=["auditoria"])

Accion = Literal["login", "caja", "venta", "cuenta", "credito", "gasto", "compra",
                 "inventario", "cliente", "torneo", "documento", "usuario", "sistema"]


@router.get("")
def get_auditoria(
    desde: dt.date | None = None,
    hasta: dt.date | None = None,
    usuario_id: uuid.UUID | None = None,
    accion: Accion | None = None,
    antes: uuid.UUID | None = None,
    limite: int = Query(100, ge=1, le=500),
    _: Usuario = Depends(requiere_permiso("auditoria.ver")),
):
    with transaccion() as conn:
        return listar_auditoria(conn, desde=desde, hasta=hasta, usuario_id=usuario_id,
                                accion=accion, antes=antes, limite=limite)
