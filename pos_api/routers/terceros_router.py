"""pos_api/routers/terceros_router.py — clientes y proveedores (terceros).

Cualquier usuario con sesión consulta, registra y edita datos de terceros
(el cajero registra clientes al vender); el cupo y los días de crédito y el
rol de proveedor tienen su propio permiso (lo valida el servicio).
"""
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from pos_api.db import transaccion
from pos_api.modelos import Dinero, Texto, TextoOpcional, cambios_enviados
from pos_api.seguridad import Usuario, usuario_actual
from pos_api.servicios import terceros as servicio

router = APIRouter(prefix="/terceros", tags=["terceros"])

DiasCredito = Annotated[int, Field(gt=0, le=365)]


class DatosCliente(BaseModel):
    limite_credito: Dinero | None = None
    dias_credito: DiasCredito | None = None
    activo: bool | None = None


class DatosProveedor(BaseModel):
    contacto: TextoOpcional = None
    activo: bool | None = None


class CrearTercero(BaseModel):
    tipo_persona: Literal["natural", "juridica"] = "natural"
    nombre: Texto
    tipo_identificacion: str | None = None
    numero_identificacion: TextoOpcional = None
    direccion: TextoOpcional = None
    municipio_id: uuid.UUID | None = None
    telefono: TextoOpcional = None
    email: TextoOpcional = None
    responsable_iva: bool | None = None
    responsabilidades: list[str] | None = None
    cliente: DatosCliente | None = None
    proveedor: DatosProveedor | None = None


class EditarTercero(BaseModel):
    tipo_persona: Literal["natural", "juridica"] | None = None
    nombre: Texto | None = None
    tipo_identificacion: str | None = None
    numero_identificacion: TextoOpcional = None
    direccion: TextoOpcional = None
    municipio_id: uuid.UUID | None = None
    telefono: TextoOpcional = None
    email: TextoOpcional = None
    responsable_iva: bool | None = None
    responsabilidades: list[str] | None = None
    cliente: DatosCliente | None = None
    proveedor: DatosProveedor | None = None


# Un null en estos significa "borrar el dato"; en tipo_persona y nombre se ignora.
_OBLIGATORIOS = {"tipo_persona", "nombre", "responsabilidades"}


@router.get("")
def get_terceros(rol: Literal["cliente", "proveedor"] | None = None, q: str | None = None,
                 activos: bool = False, limite: int = Query(200, ge=1, le=500),
                 _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.listar_terceros(conn, rol=rol, texto=q, solo_activos=activos, limite=limite)


@router.get("/responsabilidades")
def get_responsabilidades(_: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.listar_responsabilidades(conn)


@router.get("/{tercero_id}")
def get_tercero(tercero_id: uuid.UUID, _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.obtener_tercero(conn, tercero_id)


@router.post("", status_code=status.HTTP_201_CREATED)
def post_tercero(body: CrearTercero, actor: Usuario = Depends(usuario_actual)):
    datos = body.model_dump(exclude={"responsabilidades", "cliente", "proveedor"})
    cliente = cambios_enviados(body.cliente) if body.cliente is not None else None
    proveedor = cambios_enviados(body.proveedor, obligatorios={"activo"}) if body.proveedor is not None else None
    with transaccion() as conn:
        return servicio.crear_tercero(conn, actor, datos, body.responsabilidades, cliente, proveedor)


@router.patch("/{tercero_id}")
def patch_tercero(tercero_id: uuid.UUID, body: EditarTercero, actor: Usuario = Depends(usuario_actual)):
    cambios = cambios_enviados(body, obligatorios=_OBLIGATORIOS | {"cliente", "proveedor"})
    responsabilidades = cambios.pop("responsabilidades", None)
    cambios.pop("cliente", None), cambios.pop("proveedor", None)
    cliente = cambios_enviados(body.cliente) if body.cliente is not None else None
    proveedor = cambios_enviados(body.proveedor, obligatorios={"activo"}) if body.proveedor is not None else None
    with transaccion() as conn:
        return servicio.editar_tercero(conn, actor, tercero_id, cambios, responsabilidades, cliente, proveedor)


@router.put("/{tercero_id}/cliente")
def put_cliente(tercero_id: uuid.UUID, body: DatosCliente, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.guardar_cliente(conn, actor, tercero_id, cambios_enviados(body))


@router.put("/{tercero_id}/proveedor")
def put_proveedor(tercero_id: uuid.UUID, body: DatosProveedor, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.guardar_proveedor(conn, actor, tercero_id, cambios_enviados(body, obligatorios={"activo"}))
