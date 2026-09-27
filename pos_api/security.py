"""
pos_api/security.py — El G POS (servicio web)

Login de vendedores y resolución de identidad por request.

auth.py sigue siendo la única fuente de verdad de "quién es el usuario
activo" (lo consultan modules/ventas.py, cuentas.py, caja.py sin saber que
existe un servidor web detrás). Aquí solo:
  1) emitimos un JWT al hacer login (verificando contra la misma tabla
     `usuarios` / mismo hash que usa el desktop), y
  2) en cada request, decodificamos ese JWT y llamamos a
     auth.set_sesion(...) para que el resto del código de negocio vea el
     usuario correcto — aislado por request gracias al ContextVar de auth.py.
"""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import auth
from database import get_connection, verificar_contrasena
from pos_api.config import JWT_ALGORITHM, JWT_EXPIRATION_HORAS, JWT_SECRET

_bearer = HTTPBearer(auto_error=False)


def verificar_credenciales(usuario: str, contrasena: str) -> dict | None:
    """Valida usuario/contraseña contra la base de datos (mismo esquema que
    usa el desktop). No toca auth._sesion_activa — eso ocurre solo en el
    dependency de request, para no filtrar la sesión de login entre
    peticiones."""
    conn = get_connection()
    try:
        fila = conn.execute(
            "SELECT id, usuario, contrasena_hash, rol, activo "
            "FROM usuarios WHERE usuario = ?",
            (usuario.strip(),),
        ).fetchone()
    finally:
        conn.close()

    if fila is None or not fila["activo"]:
        return None
    if not verificar_contrasena(contrasena, fila["contrasena_hash"]):
        return None
    return {"id": fila["id"], "usuario": fila["usuario"], "rol": fila["rol"]}


def crear_token(usuario: dict) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario["id"]),
        "usuario": usuario["usuario"],
        "rol": usuario["rol"],
        "iat": ahora,
        "exp": ahora + timedelta(hours=JWT_EXPIRATION_HORAS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Dependencia de FastAPI: exige un JWT válido y fija la sesión activa
    del contexto de ESTE request (auth.set_sesion), para que las funciones
    de modules/*.py (que llaman a auth.get_usuario_id()/es_admin()) vean al
    usuario correcto sin que el request de otro vendedor lo pise.

    IMPORTANTE: esta dependencia debe ser `async def`, no `def`. FastAPI
    ejecuta las dependencias y el endpoint síncronos cada uno en su propio
    hilo del threadpool (vía anyio.to_thread.run_sync), y cada hilo arranca
    con su PROPIA copia del contexto — un ContextVar.set() hecho en el hilo
    de la dependencia nunca llegaría al hilo donde corre el endpoint. Al ser
    async, esta función corre en el mismo event loop/contexto que el
    despacho posterior del endpoint, así que el set() sí se propaga."""
    if credenciales is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta token de sesión.")
    try:
        payload = jwt.decode(credenciales.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado.")

    sesion = {"id": int(payload["sub"]), "usuario": payload["usuario"], "rol": payload["rol"]}
    auth.set_sesion(sesion)
    return sesion


def requiere_admin(usuario: dict = Depends(usuario_actual)) -> dict:
    if usuario["rol"] != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Se requiere rol administrador.")
    return usuario
