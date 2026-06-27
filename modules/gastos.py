"""
modules/gastos.py — El G POS
Registro y consulta de gastos generales del negocio
(nómina, arriendo, aseo, envíos, servicios, etc.).
Reutiliza la tabla `egresos` con categoria distinta a pedidos.
"""

from database import get_connection
from auth import get_usuario_id, requiere_admin
from modules.proveedores import migrar_egresos

CATEGORIAS_GASTO = [
    "Nómina",
    "Arriendo",
    "Servicios públicos",
    "Aseo y utensilios",
    "Envíos y domicilios",
    "Mantenimiento",
    "Publicidad",
    "Otros",
]

METODOS_PAGO = ["efectivo", "transferencia", "nequi", "daviplata", "tarjeta"]


def registrar_gasto(
    concepto: str,
    total: float,
    categoria: str,
    metodo_pago: str = "efectivo",
    notas: str = None,
) -> int:
    """
    Registra un gasto general en la tabla egresos.
    Lo vincula a la sesión de caja activa si existe.
    Retorna el ID del egreso creado.
    """
    migrar_egresos()

    concepto  = concepto.strip()
    categoria = categoria.strip()
    if not concepto:
        raise ValueError("El concepto no puede estar vacío.")
    if total <= 0:
        raise ValueError("El monto debe ser mayor a cero.")
    if categoria not in CATEGORIAS_GASTO:
        raise ValueError(f"Categoría inválida: {categoria}")
    if metodo_pago not in METODOS_PAGO:
        raise ValueError(f"Método de pago inválido: {metodo_pago}")

    from modules.caja import get_sesion_activa
    sesion    = get_sesion_activa()
    sesion_id = sesion["id"] if sesion else None
    usuario_id = get_usuario_id()

    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO egresos
                (concepto, total, categoria, metodo_pago, sesion_id, usuario_id, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (concepto, total, categoria, metodo_pago, sesion_id, usuario_id, notas))

        egreso_id = cur.lastrowid

        # Descontar de totales de caja si hay sesión abierta
        if sesion_id:
            from modules.caja import METODOS_DIGITALES
            if metodo_pago in METODOS_DIGITALES:
                conn.execute(
                    "UPDATE sesiones_caja SET total_digital = total_digital - ? WHERE id = ?",
                    (total, sesion_id)
                )
            else:
                conn.execute(
                    "UPDATE sesiones_caja SET total_efectivo = total_efectivo - ? WHERE id = ?",
                    (total, sesion_id)
                )

        conn.commit()
    finally:
        conn.close()

    try:
        from modules.auditoria import registrar
        registrar(
            "gasto",
            f"Gasto registrado — {concepto} ({categoria}) — ${total:,.0f} vía {metodo_pago}",
            referencia_id=egreso_id,
        )
    except Exception:
        pass
    return egreso_id


def listar_gastos(
    fecha_inicio: str = None,
    fecha_fin: str = None,
    categoria: str = None,
    limite: int = 100,
) -> list:
    """
    Retorna gastos generales (egresos sin pedido_id asociado).
    Filtros opcionales: rango de fechas y categoría.
    """
    migrar_egresos()
    conn   = get_connection()
    query  = """
        SELECT e.id, e.fecha, e.concepto, e.categoria,
               e.total, e.metodo_pago, e.notas, u.usuario AS cajero
        FROM egresos e
        JOIN usuarios u ON e.usuario_id = u.id
        WHERE e.pedido_id IS NULL
    """
    params = []
    if fecha_inicio:
        query += " AND date(e.fecha) >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND date(e.fecha) <= ?"
        params.append(fecha_fin)
    if categoria:
        query += " AND e.categoria = ?"
        params.append(categoria)
    query += " ORDER BY e.fecha DESC LIMIT ?"
    params.append(limite)

    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def resumen_gastos_sesion(sesion_id: int) -> list:
    """Retorna los gastos generales registrados en una sesión de caja."""
    migrar_egresos()
    conn  = get_connection()
    filas = conn.execute("""
        SELECT concepto, categoria, total, metodo_pago
        FROM egresos
        WHERE sesion_id = ? AND pedido_id IS NULL
        ORDER BY fecha
    """, (sesion_id,)).fetchall()
    conn.close()
    return [dict(f) for f in filas]


@requiere_admin
def eliminar_gasto(egreso_id: int) -> None:
    """Elimina un gasto general. Solo admin."""
    migrar_egresos()
    conn = get_connection()
    try:
        egreso = conn.execute(
            "SELECT id, pedido_id FROM egresos WHERE id = ?", (egreso_id,)
        ).fetchone()
        if not egreso:
            raise ValueError("Gasto no encontrado.")
        if egreso["pedido_id"] is not None:
            raise ValueError("No se puede eliminar un egreso vinculado a un pedido.")
        conn.execute("DELETE FROM egresos WHERE id = ?", (egreso_id,))
        conn.commit()
    finally:
        conn.close()

    try:
        from modules.auditoria import registrar
        registrar("gasto", f"Gasto #{egreso_id} eliminado", referencia_id=egreso_id)
    except Exception:
        pass
