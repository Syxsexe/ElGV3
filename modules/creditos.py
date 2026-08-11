"""
modules/creditos.py — El G POS
Sistema de crédito para clientes: cargos, abonos y saldos.

Modelo:
  - clientes.limite_credito : techo de deuda total (sin vencimiento en la cuenta)
  - clientes.dias_credito   : plazo por defecto para cada compra a crédito
  - creditos(tipo='cargo')  : compra individual a crédito con fecha_vencimiento propia
  - creditos(tipo='abono')  : pago; cargo_id vincula a compra específica o NULL=general
"""

from database import get_connection
from auth import get_usuario_id


def migrar():
    """Crea / actualiza la tabla creditos y las columnas de crédito en clientes."""
    conn = get_connection()

    cols_cli = [r[1] for r in conn.execute("PRAGMA table_info(clientes)").fetchall()]
    if "limite_credito" not in cols_cli:
        conn.execute("ALTER TABLE clientes ADD COLUMN limite_credito REAL DEFAULT 0")
    if "dias_credito" not in cols_cli:
        conn.execute("ALTER TABLE clientes ADD COLUMN dias_credito INTEGER DEFAULT 30")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS creditos (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id        INTEGER NOT NULL REFERENCES clientes(id),
            tipo              TEXT    NOT NULL CHECK(tipo IN ('cargo','abono')),
            monto             REAL    NOT NULL,
            fecha             TEXT    DEFAULT (datetime('now','localtime')),
            fecha_vencimiento TEXT,
            venta_id          INTEGER REFERENCES ventas(id),
            metodo_pago       TEXT,
            sesion_id         INTEGER REFERENCES sesiones_caja(id),
            notas             TEXT
        )
    """)

    cols_cr = [r[1] for r in conn.execute("PRAGMA table_info(creditos)").fetchall()]
    if "cargo_id" not in cols_cr:
        conn.execute(
            "ALTER TABLE creditos ADD COLUMN cargo_id INTEGER REFERENCES creditos(id)"
        )

    conn.commit()
    conn.close()


# ── Consultas ─────────────────────────────────────────────────────────────────

def get_saldo(cliente_id: int) -> float:
    """Deuda actual del cliente (SUM cargos − SUM abonos). Siempre coherente."""
    migrar()
    conn = get_connection()
    fila = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN tipo='cargo' THEN monto ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN tipo='abono' THEN monto ELSE 0 END), 0) AS saldo
        FROM creditos WHERE cliente_id = ?
    """, (cliente_id,)).fetchone()
    conn.close()
    return round(fila["saldo"] if fila else 0, 2)


def get_saldo_cargo(cargo_id: int) -> float:
    """Saldo pendiente de una compra a crédito específica."""
    conn = get_connection()
    cargo = conn.execute(
        "SELECT monto FROM creditos WHERE id = ? AND tipo = 'cargo'", (cargo_id,)
    ).fetchone()
    if not cargo:
        conn.close()
        return 0.0
    pagado = conn.execute(
        "SELECT COALESCE(SUM(monto), 0) AS p FROM creditos "
        "WHERE cargo_id = ? AND tipo = 'abono'",
        (cargo_id,)
    ).fetchone()
    conn.close()
    return round(cargo["monto"] - pagado["p"], 2)


def get_info_credito(cliente_id: int) -> dict:
    """Retorna limite, saldo, disponible y días de crédito del cliente."""
    migrar()
    conn = get_connection()
    cliente = conn.execute(
        "SELECT limite_credito, dias_credito FROM clientes WHERE id = ?", (cliente_id,)
    ).fetchone()
    conn.close()
    if not cliente:
        return {"limite": 0, "saldo": 0, "disponible": 0, "dias_credito": 30}
    limite = cliente["limite_credito"] or 0
    saldo  = get_saldo(cliente_id)
    return {
        "limite":       limite,
        "saldo":        saldo,
        "disponible":   max(0, round(limite - saldo, 2)),
        "dias_credito": cliente["dias_credito"] or 30,
    }


def get_cargos_pendientes(cliente_id: int) -> list:
    """
    Compras a crédito con saldo pendiente individual.
    Cada fila incluye 'pendiente' (float) y 'vencido' (bool).
    Ordena por vencimiento más urgente primero.
    """
    migrar()
    from datetime import date
    hoy = date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    filas = conn.execute("""
        SELECT
            c.id, c.fecha, c.monto, c.fecha_vencimiento, c.venta_id, c.notas,
            COALESCE(
                (SELECT SUM(a.monto) FROM creditos a
                 WHERE a.cargo_id = c.id AND a.tipo = 'abono'),
                0
            ) AS pagado
        FROM creditos c
        WHERE c.cliente_id = ? AND c.tipo = 'cargo'
        ORDER BY c.fecha_vencimiento ASC, c.fecha ASC
    """, (cliente_id,)).fetchall()
    conn.close()
    resultado = []
    for f in filas:
        d = dict(f)
        d["pendiente"] = round(d["monto"] - d["pagado"], 2)
        if d["pendiente"] <= 0.01:
            continue
        venc = d.get("fecha_vencimiento")
        d["vencido"] = bool(venc and venc[:10] < hoy)
        resultado.append(d)
    return resultado


def listar_cargos_pendientes_todos(solo_vencidos: bool = False) -> list:
    """Cargos pendientes de todos los clientes (vista global de créditos)."""
    migrar()
    from datetime import date
    hoy = date.today().strftime("%Y-%m-%d")
    conn = get_connection()
    filas = conn.execute("""
        SELECT
            c.id, c.fecha, c.monto, c.fecha_vencimiento, c.venta_id, c.cliente_id,
            cl.nombre AS cliente_nombre,
            COALESCE(
                (SELECT SUM(a.monto) FROM creditos a
                 WHERE a.cargo_id = c.id AND a.tipo = 'abono'),
                0
            ) AS pagado
        FROM creditos c
        JOIN clientes cl ON c.cliente_id = cl.id
        WHERE c.tipo = 'cargo'
        ORDER BY c.fecha_vencimiento ASC, c.fecha ASC
    """).fetchall()
    conn.close()
    resultado = []
    for f in filas:
        d = dict(f)
        d["pendiente"] = round(d["monto"] - d["pagado"], 2)
        if d["pendiente"] <= 0.01:
            continue
        venc = d.get("fecha_vencimiento")
        d["vencido"] = bool(venc and venc[:10] < hoy)
        if solo_vencidos and not d["vencido"]:
            continue
        resultado.append(d)
    return resultado


def listar_saldos() -> list:
    """
    Clientes con límite de crédito: saldo, disponible, próx. vencimiento
    y cantidad de compras vencidas.
    """
    migrar()
    conn = get_connection()
    clientes = conn.execute("""
        SELECT id, nombre, limite_credito, dias_credito
        FROM clientes
        WHERE activo = 1 AND limite_credito > 0
        ORDER BY nombre
    """).fetchall()

    resultado = []
    for c in clientes:
        saldo      = get_saldo(c["id"])
        pendientes = get_cargos_pendientes(c["id"])
        prox_venc  = min(
            (p["fecha_vencimiento"] for p in pendientes if p.get("fecha_vencimiento")),
            default=None,
        )
        vencidos = sum(1 for p in pendientes if p.get("vencido"))
        resultado.append({
            "id":           c["id"],
            "nombre":       c["nombre"],
            "limite":       c["limite_credito"],
            "saldo":        saldo,
            "disponible":   max(0, round(c["limite_credito"] - saldo, 2)),
            "dias_credito": c["dias_credito"],
            "prox_venc":    prox_venc,
            "vencidos":     vencidos,
        })
    conn.close()
    return resultado


def historial_abonos(cliente_id: int, limite: int = 100) -> list:
    """Abonos del cliente, más recientes primero."""
    migrar()
    conn = get_connection()
    filas = conn.execute("""
        SELECT id, fecha, monto, metodo_pago, notas, cargo_id
        FROM creditos
        WHERE cliente_id = ? AND tipo = 'abono'
        ORDER BY fecha DESC
        LIMIT ?
    """, (cliente_id, limite)).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def historial_cliente(cliente_id: int, limite: int = 150) -> list:
    """Todos los movimientos de crédito de un cliente (más recientes primero)."""
    migrar()
    conn = get_connection()
    filas = conn.execute("""
        SELECT c.*, v.id AS vid
        FROM creditos c
        LEFT JOIN ventas v ON c.venta_id = v.id
        WHERE c.cliente_id = ?
        ORDER BY c.fecha DESC
        LIMIT ?
    """, (cliente_id, limite)).fetchall()
    conn.close()
    return [dict(f) for f in filas]


# ── Escritura ─────────────────────────────────────────────────────────────────

def registrar_cargo(
    cliente_id: int,
    monto: float,
    venta_id: int = None,
    notas: str = None,
) -> int:
    """
    Registra una compra a crédito.
    La fecha de vencimiento se fija según dias_credito del cliente.
    Lanza ValueError si el crédito disponible es insuficiente.
    """
    migrar()
    info = get_info_credito(cliente_id)
    if info["limite"] <= 0:
        raise ValueError("Este cliente no tiene límite de crédito asignado.")
    if monto > info["disponible"]:
        from modules.caja import formatear_pesos
        raise ValueError(
            f"Crédito insuficiente. Disponible: {formatear_pesos(info['disponible'])},"
            f" solicitado: {formatear_pesos(monto)}."
        )

    from datetime import datetime, timedelta
    venc = (datetime.now() + timedelta(days=info["dias_credito"])).strftime("%Y-%m-%d")

    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO creditos (cliente_id, tipo, monto, fecha_vencimiento, venta_id, notas)
            VALUES (?, 'cargo', ?, ?, ?, ?)
        """, (cliente_id, monto, venc, venta_id, notas))
        conn.commit()
        cargo_id = cur.lastrowid
    finally:
        conn.close()

    try:
        from modules.auditoria import registrar
        from modules.caja import formatear_pesos
        registrar(
            "cuenta",
            f"Cargo a crédito — cliente #{cliente_id} — {formatear_pesos(monto)}"
            + (f" (venta #{venta_id})" if venta_id else ""),
            referencia_id=cargo_id,
        )
    except Exception:
        pass
    return cargo_id


def registrar_abono(
    cliente_id: int,
    monto: float,
    cargo_id: int = None,
    metodo_pago: str = "efectivo",
    sesion_id: int = None,
    notas: str = None,
) -> int:
    """
    Registra un pago a la deuda del cliente.
    - cargo_id dado  → valida y aplica contra esa compra específica.
    - cargo_id=None  → abono general, valida contra saldo total.
    Actualiza la caja activa si hay sesión abierta.
    """
    migrar()
    if monto <= 0:
        raise ValueError("El monto del abono debe ser mayor a cero.")

    if cargo_id:
        pendiente = get_saldo_cargo(cargo_id)
        if pendiente <= 0:
            raise ValueError("Esta compra ya está completamente saldada.")
        if round(monto, 2) > round(pendiente, 2) + 0.01:
            from modules.caja import formatear_pesos
            raise ValueError(
                f"El pago ({formatear_pesos(monto)}) supera el pendiente "
                f"de esta compra ({formatear_pesos(pendiente)})."
            )
    else:
        saldo = get_saldo(cliente_id)
        if saldo <= 0:
            raise ValueError("Este cliente no tiene saldo pendiente.")
        if round(monto, 2) > round(saldo, 2) + 0.01:
            from modules.caja import formatear_pesos
            raise ValueError(
                f"El pago ({formatear_pesos(monto)}) supera el saldo "
                f"pendiente ({formatear_pesos(saldo)})."
            )

    # Si no se indicó sesión, se atribuye a la caja abierta al momento del pago,
    # para que el abono sume a la caja del día en que se paga.
    if sesion_id is None:
        from modules.caja import get_sesion_activa
        _s = get_sesion_activa()
        sesion_id = _s["id"] if _s else None

    conn = get_connection()
    try:
        cur = conn.execute("""
            INSERT INTO creditos
                (cliente_id, tipo, monto, metodo_pago, sesion_id, notas, cargo_id)
            VALUES (?, 'abono', ?, ?, ?, ?, ?)
        """, (cliente_id, monto, metodo_pago, sesion_id, notas, cargo_id))

        # El abono entra a la caja del turno como ingreso; el cierre lo suma
        # leyendo la tabla `creditos` (fuente de verdad), igual que ventas y
        # egresos. No se toca el acumulador de la sesión aquí.

        conn.commit()
        abono_id = cur.lastrowid
    finally:
        conn.close()

    try:
        from modules.auditoria import registrar
        from modules.caja import formatear_pesos
        destino = f" → compra #{cargo_id}" if cargo_id else " (general)"
        registrar(
            "cuenta",
            f"Abono a crédito — cliente #{cliente_id} — {formatear_pesos(monto)} vía {metodo_pago}{destino}",
            referencia_id=abono_id,
        )
    except Exception:
        pass
    return abono_id


def registrar_abono_masivo(
    cliente_id: int,
    monto: float,
    metodo_pago: str = "efectivo",
    sesion_id: int = None,
    notas: str = None,
) -> list:
    """
    Distribuye un pago en las compras más urgentes (vencimiento más próximo) primero.
    Retorna lista de IDs de abonos creados.
    """
    if monto <= 0:
        raise ValueError("El monto del abono debe ser mayor a cero.")

    saldo = get_saldo(cliente_id)
    if saldo <= 0:
        raise ValueError("Este cliente no tiene saldo pendiente.")
    if round(monto, 2) > round(saldo, 2) + 0.01:
        from modules.caja import formatear_pesos
        raise ValueError(
            f"El pago ({formatear_pesos(monto)}) supera el saldo total ({formatear_pesos(saldo)})."
        )

    pendientes = get_cargos_pendientes(cliente_id)
    abono_ids  = []
    restante   = round(monto, 2)

    for cargo in pendientes:
        if restante <= 0.01:
            break
        pagar = round(min(restante, cargo["pendiente"]), 2)
        aid = registrar_abono(
            cliente_id, pagar,
            cargo_id=cargo["id"],
            metodo_pago=metodo_pago,
            sesion_id=sesion_id,
            notas=notas or "Pago masivo",
        )
        abono_ids.append(aid)
        restante = round(restante - pagar, 2)

    return abono_ids


def set_limite_credito(cliente_id: int, limite: float, dias_credito: int = 30):
    """Actualiza el límite de crédito y el plazo por defecto del cliente."""
    migrar()
    if limite < 0:
        raise ValueError("El límite no puede ser negativo.")
    if dias_credito < 1:
        raise ValueError("Los días de crédito deben ser al menos 1.")
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE clientes SET limite_credito = ?, dias_credito = ? WHERE id = ?",
            (limite, dias_credito, cliente_id)
        )
        conn.commit()
    finally:
        conn.close()
