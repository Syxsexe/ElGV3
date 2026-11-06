"""pos_api/auditoria.py — Bitácora de acciones (tabla auditoria, solo inserción)."""


def auditar(conn, usuario_id, accion: str, detalle: str | None = None,
            entidad: str | None = None, entidad_id=None) -> None:
    """Registra una acción. usuario_id None = evento del sistema. accion es una
    de las de auditoria_accion_check (venta, caja, inventario, usuario…)."""
    conn.execute(
        "INSERT INTO auditoria (usuario_id, accion, detalle, entidad, entidad_id) VALUES (%s, %s, %s, %s, %s)",
        (usuario_id, accion, detalle, entidad, entidad_id),
    )


def listar_auditoria(conn, *, desde=None, hasta=None, usuario_id=None, accion=None,
                     antes=None, limite: int = 100) -> list[dict]:
    """Eventos del más nuevo al más viejo. desde/hasta son fechas (días
    completos en la hora del negocio). Para paginar, `antes` es el id del
    último evento recibido: los id son UUIDv7, ordenados por tiempo."""
    return conn.execute(
        """SELECT a.id, a.creado_en, a.accion, a.detalle, a.entidad, a.entidad_id,
                  a.usuario_id, u.usuario
             FROM auditoria a
             LEFT JOIN usuarios u ON u.id = a.usuario_id
            WHERE (%(desde)s::date IS NULL OR a.creado_en >= %(desde)s::date)
              AND (%(hasta)s::date IS NULL OR a.creado_en < %(hasta)s::date + 1)
              AND (%(usuario_id)s::uuid IS NULL OR a.usuario_id = %(usuario_id)s)
              AND (%(accion)s::text IS NULL OR a.accion = %(accion)s)
              AND (%(antes)s::uuid IS NULL OR a.id < %(antes)s)
            ORDER BY a.id DESC
            LIMIT %(limite)s""",
        {"desde": desde, "hasta": hasta, "usuario_id": usuario_id, "accion": accion,
         "antes": antes, "limite": limite},
    ).fetchall()
