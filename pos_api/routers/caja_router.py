"""pos_api/routers/caja_router.py — turnos de caja.

Abrir, mover plata y cerrar el turno lo hace cualquier usuario con sesión (el
cajero opera la caja); ver turnos pasados exige caja.historial.
"""
import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from pos_api.db import transaccion
from pos_api.modelos import Dinero, DineroPositivo, Texto, TextoOpcional
from pos_api.seguridad import Usuario, requiere_permiso, usuario_actual
from pos_api.servicios import caja as servicio

router = APIRouter(prefix="/caja", tags=["caja"])
historial = requiere_permiso("caja.historial")

CantidadBilletes = Annotated[int, Field(ge=0, le=1_000_000)]


class AbrirTurno(BaseModel):
    bases: dict[uuid.UUID, Dinero]
    notas: TextoOpcional = None


class Movimiento(BaseModel):
    tipo: Literal["retiro", "ingreso", "traslado"]
    caja_origen_id: uuid.UUID | None = None
    caja_destino_id: uuid.UUID | None = None
    monto: DineroPositivo
    motivo: Texto


class CerrarTurno(BaseModel):
    contados: dict[uuid.UUID, Dinero] = {}
    conteo: dict[uuid.UUID, CantidadBilletes] = {}
    notas: TextoOpcional = None


@router.get("/turno")
def get_turno_actual(_: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.turno_actual(conn)


@router.get("/denominaciones")
def get_denominaciones(_: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.denominaciones(conn)


@router.post("/turnos", status_code=status.HTTP_201_CREATED)
def post_turno(body: AbrirTurno, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.abrir_turno(conn, actor, body.bases, body.notas)


@router.post("/turnos/{sesion_id}/movimientos", status_code=status.HTTP_201_CREATED)
def post_movimiento(sesion_id: uuid.UUID, body: Movimiento, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.registrar_movimiento(conn, actor, sesion_id, body.tipo, body.caja_origen_id, body.caja_destino_id,
                                             body.monto, body.motivo)


@router.post("/turnos/{sesion_id}/cerrar")
def post_cerrar(sesion_id: uuid.UUID, body: CerrarTurno, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.cerrar_turno(conn, actor, sesion_id, body.contados, body.conteo, body.notas)


@router.get("/turnos")
def get_turnos(desde: date | None = None, hasta: date | None = None, _: Usuario = Depends(historial)):
    with transaccion() as conn:
        return servicio.historial(conn, desde=desde, hasta=hasta)


@router.get("/turnos/{sesion_id}")
def get_turno(sesion_id: uuid.UUID, _: Usuario = Depends(historial)):
    with transaccion() as conn:
        return servicio.detalle_turno(conn, sesion_id)
