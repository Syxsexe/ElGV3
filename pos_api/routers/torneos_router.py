"""pos_api/routers/torneos_router.py — torneos: registro e historial.

Cualquier usuario con sesión registra y consulta torneos.
"""
import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from pos_api.db import transaccion
from pos_api.modelos import Cantidad, Dinero, Texto, TextoOpcional
from pos_api.seguridad import Usuario, usuario_actual
from pos_api.servicios import torneos as servicio

router = APIRouter(prefix="/torneos", tags=["torneos"])


class Participante(BaseModel):
    cliente_id: uuid.UUID | None = None
    alias: TextoOpcional = None
    forma: Literal["pago", "fiado", "gratis"]
    metodo_pago_id: uuid.UUID | None = None


class Premio(BaseModel):
    producto_id: uuid.UUID
    cantidad: Cantidad


class NuevoTorneo(BaseModel):
    nombre: Texto
    juego_id: uuid.UUID
    participantes: Annotated[list[Participante], Field(min_length=1, max_length=500)]
    premios: Annotated[list[Premio], Field(max_length=100)] = []
    precio: Dinero | None = None
    sesion_id: uuid.UUID | None = None
    inscripcion_id: uuid.UUID | None = None
    notas: TextoOpcional = None


@router.get("")
def get_torneos(desde: date | None = None, hasta: date | None = None, juego_id: uuid.UUID | None = None,
                _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.listar_torneos(conn, desde=desde, hasta=hasta, juego_id=juego_id)


@router.get("/inscripcion")
def get_inscripcion(_: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.inscripcion(conn)


@router.get("/premios")
def get_premios(q: Annotated[str, Query(min_length=2, max_length=100)], _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.premios_disponibles(conn, q)


@router.get("/{torneo_id}")
def get_torneo(torneo_id: uuid.UUID, _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.detalle_torneo(conn, torneo_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def post_torneo(body: NuevoTorneo, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.registrar_torneo(
            conn, actor, nombre=body.nombre, juego_id=body.juego_id,
            participantes=[p.model_dump() for p in body.participantes], premios=[p.model_dump() for p in body.premios],
            precio=body.precio, sesion_id=body.sesion_id, inscripcion_id=body.inscripcion_id, notas=body.notas)
