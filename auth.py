"""
auth.py — El G POS
Autenticación de usuarios y manejo de sesión activa.
"""

from database import get_connection, verificar_contrasena


# ── Sesión activa (singleton en memoria) ─────────────────────────────────────
_sesion_activa: dict | None = None


def iniciar_sesion(usuario: str, contrasena: str) -> dict | None:
    """
    Verifica credenciales contra la base de datos.
    Si son correctas, guarda la sesión en memoria y la retorna.
    Retorna None si las credenciales son incorrectas o el usuario está inactivo.
    """
    global _sesion_activa

    conn = get_connection()
    cur  = conn.cursor()

    cur.execute("""
        SELECT id, usuario, contrasena_hash, rol, activo
        FROM usuarios
        WHERE usuario = ?
    """, (usuario.strip(),))

    fila = cur.fetchone()
    conn.close()

    if fila is None:
        return None  # usuario no existe

    if not fila["activo"]:
        return None  # usuario desactivado

    if not verificar_contrasena(contrasena, fila["contrasena_hash"]):
        return None  # contraseña incorrecta

    _sesion_activa = {
        "id":      fila["id"],
        "usuario": fila["usuario"],
        "rol":     fila["rol"],      # 'admin' | 'vendedor'
    }
    return _sesion_activa


def cerrar_sesion():
    """Limpia la sesión activa en memoria."""
    global _sesion_activa
    _sesion_activa = None


def get_sesion() -> dict | None:
    """Retorna el diccionario de la sesión activa, o None si no hay sesión."""
    return _sesion_activa


def get_usuario_id() -> int | None:
    """Retorna el ID del usuario activo, o None si no hay sesión."""
    return _sesion_activa["id"] if _sesion_activa else None


def get_rol() -> str | None:
    """Retorna el rol del usuario activo ('admin' | 'vendedor'), o None."""
    return _sesion_activa["rol"] if _sesion_activa else None


def es_admin() -> bool:
    """True si el usuario activo tiene rol admin."""
    return _sesion_activa is not None and _sesion_activa["rol"] == "admin"


def requiere_admin(func):
    """
    Decorador para proteger funciones que solo puede ejecutar un admin.
    Lanza PermissionError si el usuario activo no es admin.

    Uso:
        @requiere_admin
        def eliminar_producto(producto_id):
            ...
    """
    def wrapper(*args, **kwargs):
        if not es_admin():
            raise PermissionError("Se requiere rol administrador para esta acción.")
        return func(*args, **kwargs)
    return wrapper


# ── Gestión de usuarios (solo admin) ─────────────────────────────────────────
@requiere_admin
def crear_usuario(usuario: str, contrasena: str, rol: str) -> bool:
    """
    Crea un nuevo usuario en la base de datos.
    Retorna True si se creó, False si el nombre de usuario ya existe.
    """
    from database import hash_contrasena

    if rol not in ("admin", "vendedor"):
        raise ValueError("Rol inválido. Usa 'admin' o 'vendedor'.")

    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO usuarios (usuario, contrasena_hash, rol)
            VALUES (?, ?, ?)
        """, (usuario.strip(), hash_contrasena(contrasena), rol))
        conn.commit()
        return True
    except Exception:
        return False  # usuario duplicado u otro error
    finally:
        conn.close()


@requiere_admin
def cambiar_contrasena(usuario_id: int, nueva_contrasena: str) -> bool:
    """Actualiza la contraseña de un usuario. Solo admin."""
    from database import hash_contrasena

    conn = get_connection()
    try:
        conn.execute("""
            UPDATE usuarios SET contrasena_hash = ?
            WHERE id = ?
        """, (hash_contrasena(nueva_contrasena), usuario_id))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


@requiere_admin
def desactivar_usuario(usuario_id: int) -> bool:
    """Desactiva un usuario (no lo elimina). Solo admin."""
    conn = get_connection()
    try:
        conn.execute("UPDATE usuarios SET activo = 0 WHERE id = ?", (usuario_id,))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


@requiere_admin
def listar_usuarios() -> list:
    """Retorna todos los usuarios (sin contraseña). Solo admin."""
    conn = get_connection()
    filas = conn.execute("""
        SELECT id, usuario, rol, activo, creado_en
        FROM usuarios
        ORDER BY id
    """).fetchall()
    conn.close()
    return [dict(f) for f in filas]


# ── Ejecución directa (prueba rápida) ────────────────────────────────────────
if __name__ == "__main__":
    from database import inicializar
    inicializar()

    print("\n── Test de autenticación ──")

    # Login correcto
    sesion = iniciar_sesion("admin", "admin123")
    if sesion:
        print(f"✓ Login exitoso: {sesion['usuario']} ({sesion['rol']})")
    else:
        print("✗ Login falló")

    # Login con contraseña incorrecta
    resultado = iniciar_sesion("admin", "mala_clave")
    print(f"✓ Contraseña incorrecta rechazada: {resultado is None}")

    # Verificar rol
    print(f"✓ es_admin(): {es_admin()}")

    # Crear usuario vendedor
    ok = crear_usuario("vendedor1", "vend123", "vendedor")
    print(f"✓ Vendedor creado: {ok}")

    # Listar usuarios
    usuarios = listar_usuarios()
    print(f"✓ Usuarios en sistema: {len(usuarios)}")
    for u in usuarios:
        print(f"   - {u['usuario']} ({u['rol']}) activo={u['activo']}")

    # Cerrar sesión
    cerrar_sesion()
    print(f"✓ Sesión cerrada: {get_sesion() is None}")
