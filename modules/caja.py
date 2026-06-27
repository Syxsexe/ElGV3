"""
modules/caja.py — El G POS
Manejo de sesiones de caja: apertura, cierre y denominaciones COP.
"""

from database import get_connection
from auth import get_usuario_id, requiere_admin


# Denominaciones válidas en pesos colombianos
DENOMINACIONES_COP = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000, 50000, 100000]

# Métodos considerados digitales
METODOS_DIGITALES = {"transferencia", "tarjeta", "nequi", "daviplata"}


def migrar_dos_cajas():
    """Agrega columnas de caja dual si no existen (migración no destructiva)."""
    conn = get_connection()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(sesiones_caja)").fetchall()]
    for col, default in [
        ("total_efectivo",     "0"),
        ("total_digital",      "0"),
        ("monto_base_digital", "0"),
        ("diferencia_digital", "0"),
    ]:
        if col not in cols:
            conn.execute(
                f"ALTER TABLE sesiones_caja ADD COLUMN {col} REAL DEFAULT {default}"
            )
    conn.commit()
    conn.close()


# ════════════════════════════════════════════════════════════
# SESIÓN DE CAJA
# ════════════════════════════════════════════════════════════

def hay_sesion_abierta() -> bool:
    """True si existe una sesión de caja sin cerrar."""
    conn = get_connection()
    fila = conn.execute(
        "SELECT id FROM sesiones_caja WHERE cierre IS NULL LIMIT 1"
    ).fetchone()
    conn.close()
    return fila is not None


def get_sesion_activa() -> dict | None:
    """Retorna la sesión de caja abierta actualmente, o None."""
    conn = get_connection()
    fila = conn.execute("""
        SELECT s.*, u.usuario AS cajero
        FROM sesiones_caja s
        JOIN usuarios u ON s.usuario_id = u.id
        WHERE s.cierre IS NULL
        LIMIT 1
    """).fetchone()
    conn.close()
    return dict(fila) if fila else None


def abrir_caja(monto_base: float, monto_base_digital: float = 0,
               notas: str = None) -> int:
    """
    Abre una nueva sesión de caja.
    monto_base:         efectivo físico inicial en caja.
    monto_base_digital: saldo inicial en Nequi/transferencias.
    Retorna el ID de la sesión creada.
    """
    migrar_dos_cajas()

    if hay_sesion_abierta():
        raise ValueError("Ya existe una sesión de caja abierta. Ciérrela antes de abrir una nueva.")
    if monto_base < 0 or monto_base_digital < 0:
        raise ValueError("Los montos base no pueden ser negativos.")

    usuario_id = get_usuario_id()
    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO sesiones_caja
                (usuario_id, monto_base, monto_base_digital,
                 total_ventas, total_efectivo, total_digital, notas)
            VALUES (?, ?, ?, 0, 0, 0, ?)
        """, (usuario_id, monto_base, monto_base_digital, notas))
        conn.commit()
        sesion_id = cur.lastrowid
    finally:
        conn.close()

    try:
        from modules.auditoria import registrar
        registrar(
            "caja",
            f"Apertura de caja — efectivo base: {formatear_pesos(monto_base)}, "
            f"digital base: {formatear_pesos(monto_base_digital)}",
            referencia_id=sesion_id,
        )
    except Exception:
        pass
    return sesion_id


def cerrar_caja(
    denominaciones: dict,
    notas: str = None
) -> dict:
    """
    Cierra la sesión de caja activa.
    Calcula el cuadre de caja efectivo y caja digital por separado.

    denominaciones: {50: 2, 100: 5, 1000: 3, ...}
    Retorna resumen completo con ambas cajas.
    """
    migrar_dos_cajas()
    sesion = get_sesion_activa()
    if not sesion:
        raise ValueError("No hay sesión de caja abierta.")

    # ── Caja efectivo ─────────────────────────────────────────────────────────
    monto_contado = 0.0
    detalle_denom = []
    for denom in DENOMINACIONES_COP:
        cantidad = int(denominaciones.get(denom, 0))
        subtotal = denom * cantidad
        monto_contado += subtotal
        detalle_denom.append({
            "denominacion": denom,
            "cantidad":     cantidad,
            "subtotal":     subtotal,
        })

    total_efectivo       = sesion.get("total_efectivo",     0) or 0
    total_digital        = sesion.get("total_digital",      0) or 0
    monto_base_digital   = sesion.get("monto_base_digital", 0) or 0
    esperado_ef          = sesion["monto_base"] + total_efectivo
    diferencia_ef        = round(monto_contado - esperado_ef, 2)
    esperado_digital     = monto_base_digital + total_digital

    # El campo "digital" viene del entry_contado_digital de la UI
    monto_contado_digital = float(denominaciones.get("digital", esperado_digital))
    diferencia_dig        = round(monto_contado_digital - esperado_digital, 2)

    conn = get_connection()
    try:
        conn.execute("""
            UPDATE sesiones_caja
            SET cierre             = datetime('now','localtime'),
                monto_cierre       = ?,
                diferencia         = ?,
                diferencia_digital = ?,
                notas              = COALESCE(?, notas)
            WHERE id = ?
        """, (monto_contado, diferencia_ef, diferencia_dig, notas, sesion["id"]))

        conn.executemany("""
            INSERT INTO denominaciones_caja (sesion_id, denominacion, cantidad, subtotal)
            VALUES (?, ?, ?, ?)
        """, [
            (sesion["id"], d["denominacion"], d["cantidad"], d["subtotal"])
            for d in detalle_denom
        ])
        conn.commit()
    finally:
        conn.close()

    resumen = {
        "sesion_id":              sesion["id"],
        "cajero":                 sesion["cajero"],
        "apertura":               sesion["apertura"],
        "monto_base":             sesion["monto_base"],
        "monto_base_digital":     monto_base_digital,
        "total_ventas":           sesion["total_ventas"],
        "total_efectivo":         total_efectivo,
        "total_digital":          total_digital,
        "esperado_efectivo":      esperado_ef,
        "esperado_digital":       esperado_digital,
        "monto_contado":          monto_contado,
        "monto_contado_digital":  monto_contado_digital,
        "diferencia":             diferencia_ef,
        "diferencia_digital":     diferencia_dig,
        "denominaciones":         detalle_denom,
    }
    try:
        from modules.auditoria import registrar
        signo_ef  = "+" if diferencia_ef  >= 0 else ""
        signo_dig = "+" if diferencia_dig >= 0 else ""
        registrar(
            "caja",
            f"Cierre de caja — ventas: {formatear_pesos(sesion['total_ventas'])}, "
            f"dif. efectivo: {signo_ef}{formatear_pesos(diferencia_ef)}, "
            f"dif. digital: {signo_dig}{formatear_pesos(diferencia_dig)}",
            referencia_id=sesion["id"],
        )
    except Exception:
        pass
    return resumen


# ════════════════════════════════════════════════════════════
# CONSULTAS DE SESIONES
# ════════════════════════════════════════════════════════════

def obtener_sesion(sesion_id: int) -> dict | None:
    """Retorna una sesión de caja con su detalle de denominaciones."""
    conn = get_connection()
    sesion = conn.execute("""
        SELECT s.*, u.usuario AS cajero
        FROM sesiones_caja s
        JOIN usuarios u ON s.usuario_id = u.id
        WHERE s.id = ?
    """, (sesion_id,)).fetchone()

    if not sesion:
        conn.close()
        return None

    denom = conn.execute("""
        SELECT denominacion, cantidad, subtotal
        FROM denominaciones_caja
        WHERE sesion_id = ?
        ORDER BY denominacion DESC
    """, (sesion_id,)).fetchall()

    conn.close()
    return {
        **dict(sesion),
        "denominaciones": [dict(d) for d in denom],
    }


@requiere_admin
def listar_sesiones(limite: int = 60,
                    fecha_inicio: str = None,
                    fecha_fin: str = None) -> list:
    """
    Retorna sesiones de caja cerradas. Solo admin.
    fecha_inicio / fecha_fin: 'YYYY-MM-DD' filtran por fecha de apertura.
    """
    conn   = get_connection()
    query  = """
        SELECT s.*, u.usuario AS cajero
        FROM sesiones_caja s
        JOIN usuarios u ON s.usuario_id = u.id
        WHERE s.cierre IS NOT NULL
    """
    params = []
    if fecha_inicio:
        query += " AND date(s.apertura) >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND date(s.apertura) <= ?"
        params.append(fecha_fin)
    query += " ORDER BY s.apertura DESC LIMIT ?"
    params.append(limite)
    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


@requiere_admin
def resumen_sesiones(fecha_inicio: str = None, fecha_fin: str = None) -> dict:
    """
    Resumen agregado de sesiones cerradas.
    Retorna totales de ventas, diferencias y conteo de sesiones.
    Fechas en formato 'YYYY-MM-DD'.
    """
    conn   = get_connection()
    query  = """
        SELECT
            COUNT(*)              AS total_sesiones,
            SUM(total_ventas)     AS suma_ventas,
            SUM(monto_base)       AS suma_bases,
            SUM(monto_cierre)     AS suma_contado,
            SUM(diferencia)       AS suma_diferencias,
            SUM(CASE WHEN diferencia > 0 THEN 1 ELSE 0 END) AS sesiones_sobrante,
            SUM(CASE WHEN diferencia < 0 THEN 1 ELSE 0 END) AS sesiones_faltante
        FROM sesiones_caja
        WHERE cierre IS NOT NULL
    """
    params = []
    if fecha_inicio:
        query += " AND date(apertura) >= ?"
        params.append(fecha_inicio)
    if fecha_fin:
        query += " AND date(apertura) <= ?"
        params.append(fecha_fin)

    fila = conn.execute(query, params).fetchone()
    conn.close()
    return dict(fila) if fila else {}


# ════════════════════════════════════════════════════════════
# UTILIDADES
# ════════════════════════════════════════════════════════════

def calcular_desde_denominaciones(denominaciones: dict) -> float:
    """
    Calcula el total en pesos dado un dict de denominaciones.
    Útil para que la interfaz muestre el total en tiempo real.
    denominaciones: {1000: 5, 5000: 2, ...}
    """
    return sum(
        int(denom) * int(cant)
        for denom, cant in denominaciones.items()
    )


def formatear_pesos(valor: float) -> str:
    """Formatea un valor como pesos colombianos. Ej: 15000 → '$15.000'"""
    return f"${valor:,.0f}".replace(",", ".")


# ════════════════════════════════════════════════════════════
# PRUEBA DIRECTA
# ════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from database import inicializar
    from auth import iniciar_sesion

    inicializar()
    iniciar_sesion("admin", "admin123")

    print("\n── Test 1: abrir caja ──")
    if hay_sesion_abierta():
        print("  Ya hay sesión abierta, cerrando primero...")
        # cierre de emergencia para tests repetidos
        conn = get_connection()
        conn.execute("UPDATE sesiones_caja SET cierre = datetime('now') WHERE cierre IS NULL")
        conn.commit()
        conn.close()

    sesion_id = abrir_caja(monto_base=50000, notas="Turno mañana")
    print(f"  Sesión abierta ID: {sesion_id}")
    sesion = get_sesion_activa()
    print(f"  Cajero: {sesion['cajero']} | Base: {formatear_pesos(sesion['monto_base'])}")

    print("\n── Test 2: simular ventas acumuladas ──")
    conn = get_connection()
    conn.execute(
        "UPDATE sesiones_caja SET total_ventas = 87500 WHERE id = ?", (sesion_id,)
    )
    conn.commit()
    conn.close()
    print("  Ventas simuladas: $87.500")

    print("\n── Test 3: cerrar caja con denominaciones ──")
    denominaciones_contadas = {
        100000: 1,   # $100.000
        50000:  0,
        20000:  1,   # $20.000
        10000:  1,   # $10.000
        5000:   3,   # $15.000
        2000:   1,   # $2.000
        1000:   0,
        500:    1,   # $500
        200:    0,
        100:    0,
        50:     0,
        # total contado: $147.500
        # esperado: $50.000 + $87.500 = $137.500
        # diferencia: +$10.000 (sobrante)
    }

    resumen = cerrar_caja(denominaciones_contadas, notas="Cierre turno mañana")
    print(f"  Monto base:     {formatear_pesos(resumen['monto_base'])}")
    print(f"  Total ventas:   {formatear_pesos(resumen['total_ventas'])}")
    print(f"  Monto esperado: {formatear_pesos(resumen['monto_esperado'])}")
    print(f"  Monto contado:  {formatear_pesos(resumen['monto_contado'])}")
    print(f"  Diferencia:     {formatear_pesos(resumen['diferencia'])}")

    print("\n── Test 4: detalle de denominaciones ──")
    for d in resumen["denominaciones"]:
        if d["cantidad"] > 0:
            print(f"  {formatear_pesos(d['denominacion'])} × {d['cantidad']} = {formatear_pesos(d['subtotal'])}")

    print("\n── Test 5: historial de sesiones ──")
    sesiones = listar_sesiones()
    print(f"  Sesiones cerradas: {len(sesiones)}")
    for s in sesiones:
        print(f"  [{s['id']}] {s['cajero']} | ventas={formatear_pesos(s['total_ventas'])} | dif={formatear_pesos(s['diferencia'])}")

    print("\n── Test 6: doble apertura (debe fallar) ──")
    sesion_id2 = abrir_caja(monto_base=30000)
    try:
        abrir_caja(monto_base=30000)
    except ValueError as e:
        print(f"  Error esperado: {e}")
    # limpiar
    conn = get_connection()
    conn.execute("UPDATE sesiones_caja SET cierre = datetime('now') WHERE cierre IS NULL")
    conn.commit()
    conn.close()