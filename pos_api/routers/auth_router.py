"""pos_api/routers/auth_router.py — login → JWT, y quién soy."""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from pos_api.auditoria import auditar
from pos_api.db import transaccion
from pos_api.seguridad import Usuario, crear_token, usuario_actual, verificar_credenciales
from pos_api.servicios.usuarios import cambiar_mi_contrasena

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    usuario: str
    contrasena: str


class CambiarContrasena(BaseModel):
    actual: str
    nueva: str


@router.post("/login")
def login(body: LoginRequest):
    with transaccion() as conn:
        usuario = verificar_credenciales(conn, body.usuario, body.contrasena)
        if usuario is not None:
            auditar(conn, usuario.id, "login", "Inicio de sesión en la web")
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos.")
    return {"token": crear_token(usuario), **usuario.como_dict()}


@router.get("/yo")
def yo(usuario: Usuario = Depends(usuario_actual)):
    return usuario.como_dict()


@router.post("/contrasena")
def post_mi_contrasena(body: CambiarContrasena, usuario: Usuario = Depends(usuario_actual)):
    """Cambia la contraseña y cierra las demás sesiones; devuelve un token
    nuevo para que quien la cambió siga adentro."""
    with transaccion() as conn:
        cambiar_mi_contrasena(conn, usuario, body.actual, body.nueva)
    return {"token": crear_token(usuario)}
