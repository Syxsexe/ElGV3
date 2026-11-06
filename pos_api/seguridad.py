"""
pos_api/seguridad.py — Contraseñas, sesiones (JWT) y permisos.

El JWT solo lleva el id del usuario. En cada request se vuelve a leer el
usuario y sus permisos de la base: desactivar a alguien o cambiarle el rol
aplica de inmediato, sin esperar a que venza su token.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from pos_api.config import JWT_ALGORITHM, JWT_EXPIRATION_HORAS, JWT_SECRET
from pos_api.db import transaccion
from pos_api.errores import ErrorNegocio

_bearer = HTTPBearer(auto_error=False)
_hasher = PasswordHasher()  # argon2id con los parámetros recomendados por la librería
# Hash de relleno: si el usuario no existe se verifica contra este igual, para
# que la respuesta tarde lo mismo y no revele qué usuarios existen.
_HASH_RELLENO = _hasher.hash("contraseña de relleno")

LARGO_MINIMO_CONTRASENA = 8


@dataclass(frozen=True)
class Usuario:
    id: uuid.UUID
    usuario: str
    rol: str
    permisos: frozenset[str]

    def puede(self, permiso: str) -> bool:
        return permiso in self.permisos

    def como_dict(self) -> dict:
        return {"id": str(self.id), "usuario": self.usuario, "rol": self.rol, "permisos": sorted(self.permisos)}


def hash_contrasena(contrasena: str) -> str:
    if len(contrasena) < LARGO_MINIMO_CONTRASENA:
        raise ErrorNegocio(f"La contraseña debe tener al menos {LARGO_MINIMO_CONTRASENA} caracteres.")
    return _hasher.hash(contrasena)


def cargar_usuario(conn, usuario_id) -> Usuario | None:
    """El usuario activo con sus permisos, o None si no existe o está inactivo."""
    fila = conn.execute(
        """SELECT u.id, u.usuario, r.nombre AS rol,
                  COALESCE(array_agg(p.codigo) FILTER (WHERE p.codigo IS NOT NULL), '{}') AS permisos
             FROM usuarios u
             JOIN roles r ON r.id = u.rol_id
             LEFT JOIN rol_permisos rp ON rp.rol_id = r.id
             LEFT JOIN permisos p ON p.id = rp.permiso_id
            WHERE u.id = %s AND u.activo
            GROUP BY u.id, r.nombre""",
        (usuario_id,),
    ).fetchone()
    if fila is None:
        return None
    return Usuario(fila["id"], fila["usuario"], fila["rol"], frozenset(fila["permisos"]))


def verificar_credenciales(conn, usuario: str, contrasena: str) -> Usuario | None:
    """Usuario activo si la contraseña es correcta; None si no. Si el hash
    quedó con parámetros viejos, lo actualiza (conn debe estar en transacción)."""
    fila = conn.execute(
        "SELECT id, contrasena_hash, activo FROM usuarios WHERE usuario = %s",
        (usuario.strip(),),
    ).fetchone()
    hash_guardado = fila["contrasena_hash"] if fila else _HASH_RELLENO
    try:
        _hasher.verify(hash_guardado, contrasena)
    except (VerificationError, InvalidHashError):
        return None
    if fila is None or not fila["activo"]:
        return None
    if _hasher.check_needs_rehash(hash_guardado):
        conn.execute("UPDATE usuarios SET contrasena_hash = %s WHERE id = %s",
                     (_hasher.hash(contrasena), fila["id"]))
    return cargar_usuario(conn, fila["id"])


def crear_token(usuario: Usuario) -> str:
    ahora = datetime.now(timezone.utc)
    payload = {"sub": str(usuario.id), "iat": ahora, "exp": ahora + timedelta(hours=JWT_EXPIRATION_HORAS)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def usuario_actual(credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Usuario:
    """Dependencia de FastAPI: exige un JWT válido de un usuario activo."""
    if credenciales is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Falta token de sesión.")
    try:
        payload = jwt.decode(credenciales.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        usuario_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado.")
    with transaccion() as conn:
        usuario = cargar_usuario(conn, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "El usuario no existe o está desactivado.")
    return usuario


def requiere_permiso(permiso: str):
    """Dependencia que exige un permiso (ej. "caja.historial")."""
    def _dependencia(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if not usuario.puede(permiso):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tienes permiso para esta acción.")
        return usuario
    return _dependencia
