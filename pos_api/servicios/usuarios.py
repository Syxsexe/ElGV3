"""
pos_api/servicios/usuarios.py — Usuarios, roles y permisos.

Reglas que no viven en la base:
- El rol admin tiene siempre todos los permisos (las migraciones le asignan
  los nuevos por su nombre): no se edita ni se borra.
- Siempre queda al menos un usuario activo que puede gestionar usuarios; si
  no, nadie podría volver a entrar a esta pantalla.
- Nadie da más de lo que tiene: quien gestiona usuarios solo asigna roles,
  arma roles o toca usuarios cuyos permisos estén dentro de los suyos. Así un
  supervisor que crea cajeros no puede volverse admin.
"""
from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado, SinPermiso
from pos_api.seguridad import Usuario, contrasena_correcta, guardar_contrasena, hash_contrasena
from pos_api.servicios.comun import actualizar

PERMISO_GESTIONAR = "usuarios.gestionar"


def _bloquear_gestores(conn) -> None:
    """Serializa los cambios que pueden quitar gestores: sin esto, dos admins
    que se desactivan el uno al otro a la vez pasarían ambos el chequeo."""
    conn.execute("SELECT pg_advisory_xact_lock(hashtext('elg.usuarios.gestores'))")


def _exigir_gestor_activo(conn) -> None:
    """Revisa, después del cambio y en la misma transacción, que quede alguien
    activo con permiso para gestionar usuarios."""
    hay = conn.execute(
        """SELECT EXISTS (
               SELECT 1 FROM usuarios u
                 JOIN rol_permisos rp ON rp.rol_id = u.rol_id
                 JOIN permisos p ON p.id = rp.permiso_id
                WHERE u.activo AND p.codigo = %s) AS hay""",
        (PERMISO_GESTIONAR,),
    ).fetchone()["hay"]
    if not hay:
        raise ErrorNegocio("Debe quedar al menos un usuario activo con permiso para gestionar usuarios.")


def _rol(conn, rol_id) -> dict:
    rol = conn.execute(
        """SELECT r.id, r.nombre, r.descripcion,
                  COALESCE(array_agg(p.codigo) FILTER (WHERE p.codigo IS NOT NULL), '{}') AS permisos
             FROM roles r
             LEFT JOIN rol_permisos rp ON rp.rol_id = r.id
             LEFT JOIN permisos p ON p.id = rp.permiso_id
            WHERE r.id = %s
            GROUP BY r.id""",
        (rol_id,),
    ).fetchone()
    if rol is None:
        raise NoEncontrado("El rol no existe.")
    return rol


def _exigir_sin_escalar(actor: Usuario, permisos, que: str) -> None:
    faltan = set(permisos) - actor.permisos
    if faltan:
        raise SinPermiso(f"No puedes {que}: incluye permisos que tú no tienes ({', '.join(sorted(faltan))}).")


def _usuario(conn, usuario_id) -> dict:
    fila = conn.execute("SELECT id, usuario, rol_id, activo FROM usuarios WHERE id = %s FOR UPDATE",
                        (usuario_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("El usuario no existe.")
    return fila


# ── Usuarios ────────────────────────────────────────────────────────────────

def listar_usuarios(conn) -> list[dict]:
    return conn.execute(
        """SELECT u.id, u.usuario, u.activo, u.creado_en, u.rol_id, r.nombre AS rol,
                  u.tercero_id, t.nombre AS persona
             FROM usuarios u
             JOIN roles r ON r.id = u.rol_id
             LEFT JOIN terceros t ON t.id = u.tercero_id
            ORDER BY u.activo DESC, u.usuario"""
    ).fetchall()


def crear_usuario(conn, actor: Usuario, usuario: str, contrasena: str, rol_id) -> dict:
    rol = _rol(conn, rol_id)
    _exigir_sin_escalar(actor, rol["permisos"], f"crear usuarios con el rol {rol['nombre']}")
    fila = conn.execute(
        "INSERT INTO usuarios (usuario, contrasena_hash, rol_id) VALUES (%s, %s, %s) RETURNING id, usuario",
        (usuario, hash_contrasena(contrasena), rol_id),
    ).fetchone()
    auditar(conn, actor.id, "usuario", f"Creó el usuario {fila['usuario']} con el rol {rol['nombre']}",
            "usuarios", fila["id"])
    return fila


def editar_usuario(conn, actor: Usuario, usuario_id, cambios: dict) -> dict:
    """cambios: rol_id y/o activo. Solo se aplica y audita lo que cambia."""
    _bloquear_gestores(conn)
    antes = _usuario(conn, usuario_id)
    rol_actual = _rol(conn, antes["rol_id"])
    _exigir_sin_escalar(actor, rol_actual["permisos"], f"editar a {antes['usuario']}")
    cambios = {k: v for k, v in cambios.items() if antes[k] != v}
    if not cambios:
        return antes
    detalle = []
    if "rol_id" in cambios:
        rol_nuevo = _rol(conn, cambios["rol_id"])
        _exigir_sin_escalar(actor, rol_nuevo["permisos"], f"asignar el rol {rol_nuevo['nombre']}")
        detalle.append(f"rol {rol_actual['nombre']} → {rol_nuevo['nombre']}")
    if "activo" in cambios:
        detalle.append("activado" if cambios["activo"] else "desactivado")
    fila = actualizar(conn, "usuarios", usuario_id, cambios)
    _exigir_gestor_activo(conn)
    auditar(conn, actor.id, "usuario", f"Editó el usuario {fila['usuario']}: {', '.join(detalle)}",
            "usuarios", usuario_id)
    return {"id": fila["id"], "usuario": fila["usuario"], "rol_id": fila["rol_id"], "activo": fila["activo"]}


def restablecer_contrasena(conn, actor: Usuario, usuario_id, contrasena: str) -> None:
    fila = _usuario(conn, usuario_id)
    _exigir_sin_escalar(actor, _rol(conn, fila["rol_id"])["permisos"], f"cambiar la contraseña de {fila['usuario']}")
    guardar_contrasena(conn, usuario_id, contrasena)
    auditar(conn, actor.id, "usuario", f"Restableció la contraseña de {fila['usuario']}", "usuarios", usuario_id)


def cambiar_mi_contrasena(conn, actor: Usuario, actual: str, nueva: str) -> None:
    if not contrasena_correcta(conn, actor.id, actual):
        raise ErrorNegocio("La contraseña actual no es correcta.")
    guardar_contrasena(conn, actor.id, nueva)
    auditar(conn, actor.id, "usuario", "Cambió su contraseña", "usuarios", actor.id)


# ── Roles y permisos ────────────────────────────────────────────────────────

def listar_permisos(conn) -> list[dict]:
    return conn.execute("SELECT codigo, descripcion FROM permisos ORDER BY codigo").fetchall()


def listar_roles(conn) -> list[dict]:
    return conn.execute(
        """SELECT r.id, r.nombre, r.descripcion,
                  COALESCE(array_agg(p.codigo ORDER BY p.codigo) FILTER (WHERE p.codigo IS NOT NULL), '{}') AS permisos,
                  (SELECT count(*) FROM usuarios u WHERE u.rol_id = r.id) AS usuarios
             FROM roles r
             LEFT JOIN rol_permisos rp ON rp.rol_id = r.id
             LEFT JOIN permisos p ON p.id = rp.permiso_id
            GROUP BY r.id
            ORDER BY r.nombre = 'admin' DESC, r.nombre"""
    ).fetchall()


def _rol_editable(conn, actor: Usuario, rol_id, que: str) -> dict:
    conn.execute("SELECT 1 FROM roles WHERE id = %s FOR UPDATE", (rol_id,))
    rol = _rol(conn, rol_id)
    if rol["nombre"] == "admin":
        raise ErrorNegocio("El rol admin tiene siempre todos los permisos: no se edita ni se borra.")
    _exigir_sin_escalar(actor, rol["permisos"], f"{que} el rol {rol['nombre']}")
    return rol


def _asignar_permisos(conn, actor: Usuario, rol_id, permisos: list[str]) -> None:
    validos = {r["codigo"] for r in conn.execute(
        "SELECT codigo FROM permisos WHERE codigo = ANY (%s)", (permisos,))}
    desconocidos = sorted(set(permisos) - validos)
    if desconocidos:
        raise ErrorNegocio(f"Permisos desconocidos: {', '.join(desconocidos)}.")
    _exigir_sin_escalar(actor, permisos, "dar esos permisos")
    conn.execute("DELETE FROM rol_permisos WHERE rol_id = %s", (rol_id,))
    conn.execute(
        "INSERT INTO rol_permisos (rol_id, permiso_id) SELECT %s, id FROM permisos WHERE codigo = ANY (%s)",
        (rol_id, permisos),
    )


def crear_rol(conn, actor: Usuario, nombre: str, descripcion: str | None, permisos: list[str]) -> dict:
    fila = conn.execute(
        "INSERT INTO roles (nombre, descripcion) VALUES (%s, %s) RETURNING id, nombre",
        (nombre, descripcion),
    ).fetchone()
    _asignar_permisos(conn, actor, fila["id"], permisos)
    auditar(conn, actor.id, "usuario", f"Creó el rol {nombre} con permisos: {', '.join(sorted(permisos)) or 'ninguno'}",
            "roles", fila["id"])
    return fila


def editar_rol(conn, actor: Usuario, rol_id, cambios: dict, permisos: list[str] | None) -> None:
    """cambios: nombre y/o descripcion. permisos None = no tocarlos."""
    _bloquear_gestores(conn)
    rol = _rol_editable(conn, actor, rol_id, "editar")
    cambios = {k: v for k, v in cambios.items() if rol[k] != v}
    actualizar(conn, "roles", rol_id, cambios)
    detalle = [f"{k}={v}" for k, v in cambios.items()]
    if permisos is not None and set(permisos) != set(rol["permisos"]):
        _asignar_permisos(conn, actor, rol_id, permisos)
        detalle.append(f"permisos: {', '.join(sorted(permisos)) or 'ninguno'}")
    _exigir_gestor_activo(conn)
    if detalle:
        auditar(conn, actor.id, "usuario", f"Editó el rol {rol['nombre']}: {'; '.join(detalle)}", "roles", rol_id)


def borrar_rol(conn, actor: Usuario, rol_id) -> None:
    rol = _rol_editable(conn, actor, rol_id, "borrar")
    if conn.execute("SELECT EXISTS (SELECT 1 FROM usuarios WHERE rol_id = %s) AS hay", (rol_id,)).fetchone()["hay"]:
        raise ErrorNegocio("El rol tiene usuarios: asígnales otro rol antes de borrarlo.")
    conn.execute("DELETE FROM roles WHERE id = %s", (rol_id,))
    auditar(conn, actor.id, "usuario", f"Borró el rol {rol['nombre']}", "roles", rol_id)
