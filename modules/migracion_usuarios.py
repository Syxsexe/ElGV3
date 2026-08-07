"""
modules/migracion_usuarios.py — El G POS

Copia los usuarios de una base de datos VIEJA a la base actual.

El hash de contraseña es sha256 sin sal (mismo esquema en ambas versiones), así
que copiar `contrasena_hash` conserva la contraseña tal cual: los usuarios
migrados entran con la misma clave que tenían.

Por defecto NO pisa usuarios que ya existan en la base nueva (se reportan como
omitidos). Con `sobrescribir=True` los reemplaza con los de la base vieja
(incluida su contraseña) — útil si quieres traer, por ejemplo, tu admin viejo.
"""

import os
import sqlite3

from database import get_connection, DB_PATH

_ROLES_VALIDOS = {"admin", "vendedor"}


def migrar_usuarios_desde(ruta_bd_vieja: str, sobrescribir: bool = False) -> dict:
    """
    Lee la tabla `usuarios` de `ruta_bd_vieja` y la vuelca en la base actual.

    Retorna un dict:
        {
          "agregados":   [usuario, ...],   # insertados nuevos
          "actualizados":[usuario, ...],   # solo si sobrescribir=True y ya existían
          "omitidos":    [(usuario, motivo), ...],
          "errores":     [str, ...],
        }
    """
    res = {"agregados": [], "actualizados": [], "omitidos": [], "errores": []}

    ruta = os.path.abspath(os.path.expanduser(ruta_bd_vieja))
    if not os.path.exists(ruta):
        raise FileNotFoundError(f"No existe la base vieja: {ruta}")
    if os.path.abspath(str(DB_PATH)) == ruta:
        raise ValueError("La ruta indicada es la MISMA base actual; nada que migrar.")

    # Abrir la base vieja en solo-lectura para no tocarla.
    try:
        vieja = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        vieja = sqlite3.connect(ruta)  # fallback si el modo uri no está disponible
    vieja.row_factory = sqlite3.Row

    try:
        tiene = vieja.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='usuarios'"
        ).fetchone()
        if not tiene:
            raise ValueError("La base vieja no tiene tabla 'usuarios'.")

        cols_viejas = {r[1] for r in vieja.execute("PRAGMA table_info(usuarios)")}
        for req in ("usuario", "contrasena_hash", "rol"):
            if req not in cols_viejas:
                raise ValueError(f"La tabla 'usuarios' vieja no tiene la columna '{req}'.")
        tiene_activo = "activo" in cols_viejas
        tiene_creado = "creado_en" in cols_viejas

        filas = vieja.execute("SELECT * FROM usuarios").fetchall()
    finally:
        vieja.close()

    nueva = get_connection()
    try:
        existentes = {r["usuario"] for r in nueva.execute("SELECT usuario FROM usuarios")}

        for f in filas:
            usuario = (f["usuario"] or "").strip()
            hash_pw = f["contrasena_hash"]
            rol     = (f["rol"] or "").strip()
            activo  = f["activo"] if tiene_activo and f["activo"] is not None else 1
            creado  = f["creado_en"] if tiene_creado and f["creado_en"] else None

            if not usuario or not hash_pw:
                res["omitidos"].append((usuario or "(vacío)", "usuario o hash vacío"))
                continue
            if rol not in _ROLES_VALIDOS:
                res["omitidos"].append((usuario, f"rol inválido '{rol}'"))
                continue

            if usuario in existentes:
                if not sobrescribir:
                    res["omitidos"].append((usuario, "ya existe en la base nueva"))
                    continue
                nueva.execute(
                    "UPDATE usuarios SET contrasena_hash=?, rol=?, activo=? WHERE usuario=?",
                    (hash_pw, rol, activo, usuario))
                res["actualizados"].append(usuario)
            else:
                if creado:
                    nueva.execute(
                        "INSERT INTO usuarios (usuario, contrasena_hash, rol, activo, creado_en) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (usuario, hash_pw, rol, activo, creado))
                else:
                    nueva.execute(
                        "INSERT INTO usuarios (usuario, contrasena_hash, rol, activo) "
                        "VALUES (?, ?, ?, ?)",
                        (usuario, hash_pw, rol, activo))
                res["agregados"].append(usuario)
                existentes.add(usuario)

        nueva.commit()
    except Exception:
        nueva.rollback()
        raise
    finally:
        nueva.close()

    try:
        from modules.auditoria import registrar
        registrar("usuarios",
                  f"Migración de usuarios desde BD vieja: "
                  f"{len(res['agregados'])} agregados, "
                  f"{len(res['actualizados'])} actualizados, "
                  f"{len(res['omitidos'])} omitidos")
    except Exception:
        pass

    return res
