"""pos_api/routers/documentos_router.py — documentos comerciales.

Cotizaciones, órdenes de pedido y remisiones: crear, editar mientras estén
abiertas, convertir al siguiente, vender y descartar. Cualquier usuario con
sesión.
"""
import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from pos_api.db import transaccion
from pos_api.modelos import Cantidad, Dinero, TextoOpcional
from pos_api.routers.ventas_router import Pago
from pos_api.seguridad import Usuario, usuario_actual
from pos_api.servicios import documentos as servicio

router = APIRouter(prefix="/documentos", tags=["documentos"])

Tipo = Literal["cotizacion", "orden_pedido", "remision"]
Estado = Literal["abierto", "vigente", "vencida", "aceptada", "entregada", "facturada", "rechazada", "anulada"]


class Item(BaseModel):
    """Del catálogo (articulo_id; lo que falte sale del artículo) o texto libre
    (descripción y precio obligatorios)."""
    articulo_id: uuid.UUID | None = None
    descripcion: TextoOpcional = None
    cantidad: Cantidad
    precio_unit: Dinero | None = None
    impuesto_id: uuid.UUID | None = None


class DatosDocumento(BaseModel):
    cliente_id: uuid.UUID | None = None
    descuento: Dinero = 0
    vigente_hasta: date | None = None
    notas: TextoOpcional = None
    items: Annotated[list[Item], Field(min_length=1, max_length=300)]


class NuevoDocumento(DatosDocumento):
    tipo: Tipo


class Venta(BaseModel):
    sesion_id: uuid.UUID
    pagos: Annotated[list[Pago], Field(max_length=20)] = []
    fiado: Dinero = 0
    cliente_id: uuid.UUID | None = None
    notas: TextoOpcional = None


class Descarte(BaseModel):
    motivo: Literal["rechazado", "anulado"]
    explicacion: TextoOpcional = None


def _datos(body: DatosDocumento) -> dict:
    return {"cliente_id": body.cliente_id, "descuento": body.descuento, "vigente_hasta": body.vigente_hasta,
            "notas": body.notas}


@router.get("")
def get_documentos(tipo: Tipo | None = None, estado: Estado | None = None, q: str | None = None,
                   _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.listar_documentos(conn, tipo=tipo, estado=estado, texto=q)


@router.get("/{documento_id}")
def get_documento(documento_id: uuid.UUID, _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.detalle_documento(conn, documento_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def post_documento(body: NuevoDocumento, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.crear_documento(conn, actor, body.tipo, [i.model_dump() for i in body.items], **_datos(body))


@router.put("/{documento_id}")
def put_documento(documento_id: uuid.UUID, body: DatosDocumento, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.editar_documento(conn, actor, documento_id, [i.model_dump() for i in body.items], **_datos(body))


@router.post("/{documento_id}/convertir", status_code=status.HTTP_201_CREATED)
def post_convertir(documento_id: uuid.UUID, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.convertir(conn, actor, documento_id)


@router.post("/{documento_id}/vender", status_code=status.HTTP_201_CREATED)
def post_vender(documento_id: uuid.UUID, body: Venta, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.vender(conn, actor, documento_id, body.sesion_id, pagos=[p.model_dump() for p in body.pagos],
                               fiado=body.fiado, cliente_id=body.cliente_id, notas=body.notas)


@router.post("/{documento_id}/descartar")
def post_descartar(documento_id: uuid.UUID, body: Descarte, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.descartar(conn, actor, documento_id, body.motivo, body.explicacion)
