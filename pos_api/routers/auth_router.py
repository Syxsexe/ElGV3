"""pos_api/routers/auth_router.py — login de vendedores → JWT."""
from fastapi import APIRouter, HTTPException, status

from pos_api.schemas import LoginRequest, LoginResponse
from pos_api.security import crear_token, verificar_credenciales

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest):
    usuario = verificar_credenciales(body.usuario, body.contrasena)
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos.")
    token = crear_token(usuario)
    return LoginResponse(token=token, usuario=usuario["usuario"], rol=usuario["rol"])
