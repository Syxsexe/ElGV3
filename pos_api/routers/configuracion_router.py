"""pos_api/routers/configuracion_router.py — datos del negocio y catálogos.

Leer es para cualquier usuario con sesión (las pantallas de venta y caja
necesitan métodos de pago, mesas, juegos…); cambiar exige configuracion.editar.
"""
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, BeforeValidator, Field

from pos_api.db import transaccion
from pos_api.errores import NoEncontrado
from pos_api.modelos import Texto, TextoOpcional, cambios_enviados
from pos_api.seguridad import Usuario, requiere_permiso, usuario_actual
from pos_api.servicios import configuracion as servicio

router = APIRouter(prefix="/config", tags=["configuracion"])
editor = requiere_permiso("configuracion.editar")
Catalogo = Literal["mesas", "categorias-gasto", "juegos"]


# Texto libre al pie del ticket; vacío = sin texto (el límite va después del strip).
MensajeTicket = Annotated[str | None, Field(max_length=300),
                          BeforeValidator(lambda v: (v.strip() or None) if isinstance(v, str) else v)]


class EditarEmpresa(BaseModel):
    tipo_persona: Literal["natural", "juridica"] | None = None
    nombre: Texto | None = None
    tipo_identificacion: str | None = None
    numero_identificacion: Texto | None = None
    direccion: TextoOpcional = None
    municipio_id: uuid.UUID | None = None
    telefono: TextoOpcional = None
    email: TextoOpcional = None
    responsable_iva: bool | None = None
    regimen_tributario: Literal["ordinario", "simple"] | None = None
    responsable_inc: bool | None = None
    precios_incluyen_impuestos: bool | None = None
    mensaje_ticket: MensajeTicket = None


# Columnas NOT NULL: un null enviado se ignora en vez de romper la fila.
_EMPRESA_OBLIGATORIOS = {"tipo_persona", "nombre", "tipo_identificacion", "numero_identificacion",
                         "regimen_tributario", "responsable_inc", "precios_incluyen_impuestos"}


class CrearCaja(BaseModel):
    nombre: Texto
    usa_denominaciones: bool = False


class EditarCaja(BaseModel):
    nombre: Texto | None = None
    usa_denominaciones: bool | None = None
    activo: bool | None = None


class CrearMetodo(BaseModel):
    nombre: Texto
    caja_id: uuid.UUID


class EditarMetodo(BaseModel):
    nombre: Texto | None = None
    caja_id: uuid.UUID | None = None
    activo: bool | None = None


class CrearItem(BaseModel):
    nombre: Texto


class EditarItem(BaseModel):
    nombre: Texto | None = None
    activo: bool | None = None


# ── Empresa ─────────────────────────────────────────────────────────────────

@router.get("/empresa")
def get_empresa(_: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        empresa = servicio.obtener_empresa(conn)
    if empresa is None:
        raise NoEncontrado("El negocio no está configurado.")
    return empresa


@router.patch("/empresa")
def patch_empresa(body: EditarEmpresa, actor: Usuario = Depends(editor)):
    with transaccion() as conn:
        return servicio.editar_empresa(conn, actor, cambios_enviados(body, _EMPRESA_OBLIGATORIOS))


@router.get("/tipos-identificacion")
def get_tipos_identificacion(_: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.tipos_identificacion(conn)


@router.get("/municipios")
def get_municipios(q: str = Query(min_length=2), _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.buscar_municipios(conn, q)


# ── Cajas y métodos de pago ─────────────────────────────────────────────────

@router.get("/cajas")
def get_cajas(_: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.listar_cajas(conn)


@router.post("/cajas", status_code=status.HTTP_201_CREATED)
def post_caja(body: CrearCaja, actor: Usuario = Depends(editor)):
    with transaccion() as conn:
        return servicio.crear_caja(conn, actor, body.nombre, body.usa_denominaciones)


@router.patch("/cajas/{caja_id}")
def patch_caja(caja_id: uuid.UUID, body: EditarCaja, actor: Usuario = Depends(editor)):
    with transaccion() as conn:
        return servicio.editar_caja(conn, actor, caja_id, cambios_enviados(body))


@router.get("/metodos-pago")
def get_metodos_pago(_: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.metodos_activos(conn)


@router.post("/metodos-pago", status_code=status.HTTP_201_CREATED)
def post_metodo(body: CrearMetodo, actor: Usuario = Depends(editor)):
    with transaccion() as conn:
        return servicio.crear_metodo(conn, actor, body.nombre, body.caja_id)


@router.patch("/metodos-pago/{metodo_id}")
def patch_metodo(metodo_id: uuid.UUID, body: EditarMetodo, actor: Usuario = Depends(editor)):
    with transaccion() as conn:
        return servicio.editar_metodo(conn, actor, metodo_id, cambios_enviados(body))


# ── Mesas, categorías de gasto y juegos ─────────────────────────────────────

@router.get("/{catalogo}")
def get_catalogo(catalogo: Catalogo, todos: bool = False, _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.listar_catalogo(conn, catalogo, solo_activos=not todos)


@router.post("/{catalogo}", status_code=status.HTTP_201_CREATED)
def post_catalogo(catalogo: Catalogo, body: CrearItem, actor: Usuario = Depends(editor)):
    with transaccion() as conn:
        return servicio.crear_en_catalogo(conn, actor, catalogo, body.nombre)


@router.patch("/{catalogo}/{item_id}")
def patch_catalogo(catalogo: Catalogo, item_id: uuid.UUID, body: EditarItem, actor: Usuario = Depends(editor)):
    with transaccion() as conn:
        return servicio.editar_en_catalogo(conn, actor, catalogo, item_id, cambios_enviados(body))
