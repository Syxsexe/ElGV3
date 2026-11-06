"""pos_api/routers/usuarios_router.py — usuarios, roles y permisos (usuarios.gestionar)."""
import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from pos_api.db import transaccion
from pos_api.modelos import Texto, TextoOpcional, cambios_enviados
from pos_api.seguridad import Usuario, requiere_permiso
from pos_api.servicios import usuarios as servicio

router = APIRouter(tags=["usuarios"])
gestor = requiere_permiso(servicio.PERMISO_GESTIONAR)


class CrearUsuario(BaseModel):
    usuario: Texto
    contrasena: str
    rol_id: uuid.UUID


class EditarUsuario(BaseModel):
    rol_id: uuid.UUID | None = None
    activo: bool | None = None


class NuevaContrasena(BaseModel):
    contrasena: str


class CrearRol(BaseModel):
    nombre: Texto
    descripcion: TextoOpcional = None
    permisos: list[str] = []


class EditarRol(BaseModel):
    nombre: Texto | None = None
    descripcion: TextoOpcional = None
    permisos: list[str] | None = None


@router.get("/usuarios")
def get_usuarios(_: Usuario = Depends(gestor)):
    with transaccion() as conn:
        return servicio.listar_usuarios(conn)


@router.post("/usuarios", status_code=status.HTTP_201_CREATED)
def post_usuario(body: CrearUsuario, actor: Usuario = Depends(gestor)):
    with transaccion() as conn:
        return servicio.crear_usuario(conn, actor, body.usuario, body.contrasena, body.rol_id)


@router.patch("/usuarios/{usuario_id}")
def patch_usuario(usuario_id: uuid.UUID, body: EditarUsuario, actor: Usuario = Depends(gestor)):
    with transaccion() as conn:
        return servicio.editar_usuario(conn, actor, usuario_id, cambios_enviados(body))


@router.post("/usuarios/{usuario_id}/contrasena")
def post_contrasena(usuario_id: uuid.UUID, body: NuevaContrasena, actor: Usuario = Depends(gestor)):
    with transaccion() as conn:
        servicio.restablecer_contrasena(conn, actor, usuario_id, body.contrasena)
    return {"ok": True}


@router.get("/permisos")
def get_permisos(_: Usuario = Depends(gestor)):
    with transaccion() as conn:
        return servicio.listar_permisos(conn)


@router.get("/roles")
def get_roles(_: Usuario = Depends(gestor)):
    with transaccion() as conn:
        return servicio.listar_roles(conn)


@router.post("/roles", status_code=status.HTTP_201_CREATED)
def post_rol(body: CrearRol, actor: Usuario = Depends(gestor)):
    with transaccion() as conn:
        return servicio.crear_rol(conn, actor, body.nombre, body.descripcion, body.permisos)


@router.patch("/roles/{rol_id}")
def patch_rol(rol_id: uuid.UUID, body: EditarRol, actor: Usuario = Depends(gestor)):
    cambios = cambios_enviados(body, obligatorios={"nombre"})
    cambios.pop("permisos", None)
    with transaccion() as conn:
        servicio.editar_rol(conn, actor, rol_id, cambios, body.permisos)
    return {"ok": True}


@router.delete("/roles/{rol_id}")
def delete_rol(rol_id: uuid.UUID, actor: Usuario = Depends(gestor)):
    with transaccion() as conn:
        servicio.borrar_rol(conn, actor, rol_id)
    return {"ok": True}
