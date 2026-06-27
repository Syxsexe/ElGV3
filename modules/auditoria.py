"""
modules/auditoria.py — El G POS
Registro de actividad por usuario (auditoría).
"""

from database import get_connection
import auth


# ── Categorías de acción ──────────────────────────────────────────────────────
ACCIONES = {
    "login":       "Login / Sesión",
    "caja":        "Caja",
    "venta":       "Venta",
    "cuenta":      "Cuenta",
    "gasto":       "Gasto",
    "inventario":  "Inventario",
    "sistema":     "Sistema",
}


def _migrar():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha        TEXT    DEFAULT (datetime('now','localtime')),
            usuario_id   INTEGER,
            usuario      TEXT,
            accion       TEXT    NOT NULL,
            detalle      TEXT,
            referencia_id INTEGER
        )
    """)
    conn.commit()
    conn.close()


def registrar(accion: str, detalle: str, referencia_id: int = None):
    """
    Registra un evento de auditoría.
    Toma el usuario de la sesión activa (puede ser None si no hay sesión).
    """
    _migrar()
    sesion = auth.get_sesion()
    uid    = sesion["id"]      if sesion else None
    uname  = sesion["usuario"] if sesion else "—"

    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO auditoria (usuario_id, usuario, accion, detalle, referencia_id)
            VALUES (?, ?, ?, ?, ?)
        """, (uid, uname, accion, detalle, referencia_id))
        conn.commit()
    finally:
        conn.close()


def listar(
    fecha_inicio: str = None,
    fecha_fin: str = None,
    usuario_id: int = None,
    accion: str = None,
    texto: str = None,
    limite: int = 300,
) -> list:
    """Retorna eventos de auditoría con filtros opcionales."""
    _migrar()
    query  = "SELECT * FROM auditoria WHERE 1=1"
    params = []

    if fecha_inicio:
        query += " AND date(fecha) >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND date(fecha) <= ?"
        params.append(fecha_fin)
    if usuario_id:
        query += " AND usuario_id = ?"
        params.append(usuario_id)
    if accion:
        query += " AND accion = ?"
        params.append(accion)
    if texto:
        query += " AND (detalle LIKE ? OR usuario LIKE ?)"
        params += [f"%{texto}%", f"%{texto}%"]

    query += " ORDER BY fecha DESC LIMIT ?"
    params.append(limite)

    conn = get_connection()
    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def listar_usuarios_con_actividad() -> list:
    """Retorna lista de usuarios distintos que aparecen en la auditoría."""
    _migrar()
    conn  = get_connection()
    filas = conn.execute(
        "SELECT DISTINCT usuario_id, usuario FROM auditoria WHERE usuario_id IS NOT NULL ORDER BY usuario"
    ).fetchall()
    conn.close()
    return [dict(f) for f in filas]
