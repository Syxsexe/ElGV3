"""pos_api/auditoria.py — Bitácora de acciones (tabla auditoria, solo inserción)."""


def auditar(conn, usuario_id, accion: str, detalle: str | None = None,
            entidad: str | None = None, entidad_id=None) -> None:
    """Registra una acción. usuario_id None = evento del sistema. accion es una
    de las de auditoria_accion_check (venta, caja, inventario, usuario…)."""
    conn.execute(
        "INSERT INTO auditoria (usuario_id, accion, detalle, entidad, entidad_id) VALUES (%s, %s, %s, %s, %s)",
        (usuario_id, accion, detalle, entidad, entidad_id),
    )
