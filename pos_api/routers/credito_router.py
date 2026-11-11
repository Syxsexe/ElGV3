"""pos_api/routers/credito_router.py — fiado: saldos, abonos, cargos y condonaciones.

Ver saldos y recibir abonos: cualquier usuario con sesión (el cajero cobra el
fiado). Cargo manual: clientes.editar. Condonar: creditos.condonar.
"""
import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from pos_api.db import transaccion
from pos_api.modelos import DineroPositivo, Texto, TextoOpcional
from pos_api.seguridad import Usuario, requiere_permiso, usuario_actual
from pos_api.servicios import credito as servicio

router = APIRouter(prefix="/creditos", tags=["crédito"])
editor_clientes = requiere_permiso("clientes.editar")
condonador = requiere_permiso("creditos.condonar")


class Aplicacion(BaseModel):
    cargo_id: uuid.UUID
    monto: DineroPositivo


class Abono(BaseModel):
    """En el turno que el cajero tiene en pantalla. Sin aplicaciones se pagan
    primero los cargos que vencen antes."""
    sesion_id: uuid.UUID
    metodo_pago_id: uuid.UUID
    monto: DineroPositivo
    aplicaciones: Annotated[list[Aplicacion], Field(max_length=300)] | None = None
    notas: TextoOpcional = None


class Cargo(BaseModel):
    monto: DineroPositivo
    notas: Texto
    vence_en: date | None = None


class Condonacion(BaseModel):
    monto: DineroPositivo
    motivo: Texto


@router.get("")
def get_saldos(q: str | None = None, limite: int = Query(200, ge=1, le=500), _: Usuario = Depends(usuario_actual)):
    # Los totales de la cartera no dependen de la búsqueda: solo van sin texto.
    with transaccion() as conn:
        return {"cartera": None if q and q.strip() else servicio.resumen_cartera(conn),
                "clientes": servicio.listar_saldos(conn, q, limite)}


@router.get("/{cliente_id}")
def get_credito(cliente_id: uuid.UUID, _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.detalle_credito(conn, cliente_id)


@router.post("/{cliente_id}/abonos", status_code=status.HTTP_201_CREATED)
def post_abono(cliente_id: uuid.UUID, body: Abono, actor: Usuario = Depends(usuario_actual)):
    aplicaciones = [a.model_dump() for a in body.aplicaciones] if body.aplicaciones else None
    with transaccion() as conn:
        return servicio.registrar_abono(conn, actor, cliente_id, body.sesion_id, body.metodo_pago_id, body.monto,
                                        aplicaciones, body.notas)


@router.post("/{cliente_id}/cargos", status_code=status.HTTP_201_CREATED)
def post_cargo(cliente_id: uuid.UUID, body: Cargo, actor: Usuario = Depends(editor_clientes)):
    with transaccion() as conn:
        return servicio.registrar_cargo(conn, actor, cliente_id, body.monto, body.notas, body.vence_en)


@router.post("/cargos/{cargo_id}/condonar", status_code=status.HTTP_201_CREATED)
def post_condonar(cargo_id: uuid.UUID, body: Condonacion, actor: Usuario = Depends(condonador)):
    with transaccion() as conn:
        return servicio.condonar(conn, actor, cargo_id, body.monto, body.motivo)
