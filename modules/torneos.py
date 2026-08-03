"""
modules/torneos.py — El G POS
Torneos de TCG: registra la inscripción de cada jugador (con su método de pago,
incluido crédito ligado a su cliente) y los sobres/productos entregados como
premio (salen del inventario).

Con esto:
  • el conteo de dinero cuadra (cada inscripción entra a caja por su método),
  • un jugador puede inscribirse a CRÉDITO → queda un cargo en su cuenta de
    cliente para cobrarlo después,
  • los sobres de premio se descuentan del inventario, y
  • ganancia_torneo = recaudado − costo de los premios entregados.
"""
from __future__ import annotations

from database import get_connection

_METODOS_CAJA = {"efectivo", "transferencia", "tarjeta", "nequi", "daviplata"}
_METODOS = _METODOS_CAJA | {"credito"}


def registrar_torneo(
    nombre: str,
    participantes: list[dict],
    premios: list[dict] | None = None,
    juego: str | None = None,
    num_jugadores: int | None = None,
    notas: str | None = None,
) -> dict:
    """
    Registra un torneo en una sola transacción.

    participantes: [{"nombre", "monto", "metodo_pago", "cliente_id"(opt)}, ...]
        - metodo_pago 'credito' EXIGE cliente_id (se crea un cargo a su crédito).
        - los demás métodos entran a la caja activa por su método.
    premios: [{"producto_id", "cantidad"}, ...]  → se descuentan del inventario.

    Retorna resumen: {torneo_id, recaudado, costo_premios, ganancia, venta_id,
                      sesion_id, participantes:[...], premios:[...]}.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El torneo necesita un nombre.")

    # ── Normalizar participantes ──────────────────────────────────────────────
    parts = []
    for p in participantes or []:
        monto = float(p.get("monto") or 0)
        if monto <= 0:
            continue
        metodo = (p.get("metodo_pago") or "efectivo").strip()
        if metodo not in _METODOS:
            raise ValueError(f"Método de pago inválido: {metodo}")
        cid = p.get("cliente_id")
        pnombre = (p.get("nombre") or "").strip()
        if metodo == "credito" and not cid:
            raise ValueError(
                f"La inscripción a crédito de '{pnombre or 'jugador'}' "
                "necesita un cliente registrado.")
        parts.append({
            "nombre":      pnombre or "Jugador",
            "monto":       monto,
            "metodo_pago": metodo,
            "cliente_id":  cid,
            "cargo_id":    None,
        })

    premios = premios or []
    recaudado = round(sum(p["monto"] for p in parts), 2)

    # ── Validar cupo de crédito por adelantado ────────────────────────────────
    from modules.creditos import migrar as _cred_migrar, get_info_credito
    _cred_migrar()
    usado_por_cliente = {}
    for p in parts:
        if p["metodo_pago"] != "credito":
            continue
        info = get_info_credito(p["cliente_id"])
        if info["limite"] <= 0:
            raise ValueError(
                f"'{p['nombre']}' no tiene límite de crédito asignado.")
        usado_por_cliente[p["cliente_id"]] = (
            usado_por_cliente.get(p["cliente_id"], 0) + p["monto"])
        if usado_por_cliente[p["cliente_id"]] > info["disponible"]:
            from modules.caja import formatear_pesos
            raise ValueError(
                f"Crédito insuficiente para '{p['nombre']}'. "
                f"Disponible: {formatear_pesos(info['disponible'])}.")
        p["_dias"] = info["dias_credito"]

    from modules.caja import get_sesion_activa
    sesion = get_sesion_activa()
    sesion_id = sesion["id"] if sesion else None

    from auth import get_usuario_id
    usuario_id = get_usuario_id()

    conn = get_connection()
    try:
        # 1. Validar y descontar premios (snapshot de costo).
        lineas = []
        for pr in premios:
            pid = pr.get("producto_id")
            cant = float(pr.get("cantidad") or 0)
            if not pid or cant <= 0:
                continue
            row = conn.execute(
                "SELECT nombre, stock, precio_costo FROM productos WHERE id = ?",
                (pid,)).fetchone()
            if not row:
                raise ValueError(f"Producto {pid} no encontrado.")
            if row["stock"] < cant:
                raise ValueError(
                    f"Stock insuficiente de '{row['nombre']}' para el premio. "
                    f"Disponible: {row['stock']}, requerido: {cant}")
            costo_unit = row["precio_costo"] or 0
            lineas.append({
                "producto_id": pid, "nombre": row["nombre"], "cantidad": cant,
                "costo_unit": costo_unit, "subtotal": round(costo_unit * cant, 2),
            })
        for l in lineas:
            conn.execute("UPDATE productos SET stock = stock - ? WHERE id = ?",
                         (l["cantidad"], l["producto_id"]))

        costo_premios = round(sum(l["subtotal"] for l in lineas), 2)
        ganancia = round(recaudado - costo_premios, 2)

        # 2. Registrar el ingreso de las inscripciones (una venta con el desglose
        #    por método en pagos_venta) ligada a la caja activa.
        venta_id = None
        if recaudado > 0:
            from datetime import datetime
            fecha_ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            metodos = {p["metodo_pago"] for p in parts}
            metodo_final = "mixto" if len(metodos) > 1 else next(iter(metodos))
            cur = conn.execute("""
                INSERT INTO ventas
                    (fecha, total, descuento, metodo_pago, tipo,
                     usuario_id, sesion_id, notas)
                VALUES (?, ?, 0, ?, 'tienda', ?, ?, ?)
            """, (fecha_ahora, recaudado, metodo_final, usuario_id, sesion_id,
                  f"Torneo: {nombre}"))
            venta_id = cur.lastrowid
            conn.execute("""
                INSERT INTO detalle_venta
                    (venta_id, producto_id, combo_id, cantidad, precio_unit, subtotal)
                VALUES (?, NULL, NULL, 1, ?, ?)
            """, (venta_id, recaudado, recaudado))
            for p in parts:
                conn.execute("""
                    INSERT INTO pagos_venta (venta_id, metodo, monto)
                    VALUES (?, ?, ?)
                """, (venta_id, p["metodo_pago"], p["monto"]))
            from modules.ventas import _actualizar_cajas_sesion
            _actualizar_cajas_sesion(
                conn, sesion_id,
                [{"metodo": p["metodo_pago"], "monto": p["monto"]} for p in parts],
                signo=1)

        # 3. Cargos a crédito (dentro de la misma transacción).
        from datetime import datetime as _dt, timedelta
        for p in parts:
            if p["metodo_pago"] != "credito":
                continue
            venc = (_dt.now() + timedelta(days=p.get("_dias", 30))).strftime("%Y-%m-%d")
            cur = conn.execute("""
                INSERT INTO creditos
                    (cliente_id, tipo, monto, fecha_vencimiento, venta_id, notas)
                VALUES (?, 'cargo', ?, ?, ?, ?)
            """, (p["cliente_id"], p["monto"], venc, venta_id,
                  f"Inscripción torneo: {nombre}"))
            p["cargo_id"] = cur.lastrowid

        # 4. Guardar torneo, participantes y premios.
        cur = conn.execute("""
            INSERT INTO torneos
                (nombre, juego, num_jugadores, recaudado, costo_premios,
                 ganancia, usuario_id, sesion_id, venta_id, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nombre, (juego or "").strip() or None,
              int(num_jugadores) if num_jugadores is not None else len(parts),
              recaudado, costo_premios, ganancia, usuario_id, sesion_id,
              venta_id, (notas or "").strip() or None))
        torneo_id = cur.lastrowid

        for p in parts:
            conn.execute("""
                INSERT INTO torneo_participantes
                    (torneo_id, cliente_id, nombre, monto, metodo_pago, cargo_id)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (torneo_id, p["cliente_id"], p["nombre"], p["monto"],
                  p["metodo_pago"], p["cargo_id"]))

        for l in lineas:
            conn.execute("""
                INSERT INTO torneo_premios
                    (torneo_id, producto_id, nombre, cantidad, costo_unit, subtotal_costo)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (torneo_id, l["producto_id"], l["nombre"], l["cantidad"],
                  l["costo_unit"], l["subtotal"]))

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    try:
        from modules.auditoria import registrar
        registrar(
            "torneo",
            f"Torneo '{nombre}' — {len(parts)} inscritos, recaudado "
            f"${recaudado:,.0f}, costo premios ${costo_premios:,.0f}, "
            f"ganancia ${ganancia:,.0f}",
            referencia_id=torneo_id,
        )
    except Exception:
        pass

    return {
        "torneo_id":     torneo_id,
        "recaudado":     recaudado,
        "costo_premios": costo_premios,
        "ganancia":      ganancia,
        "venta_id":      venta_id,
        "sesion_id":     sesion_id,
        "participantes": parts,
        "premios":       lineas,
    }


def listar_torneos(limite: int = 200) -> list[dict]:
    """Lista los torneos (más recientes primero)."""
    conn = get_connection()
    try:
        filas = conn.execute("""
            SELECT t.*, u.usuario AS cajero,
                   (SELECT COUNT(*) FROM torneo_participantes tp WHERE tp.torneo_id = t.id)
                       AS num_inscritos
            FROM torneos t
            LEFT JOIN usuarios u ON t.usuario_id = u.id
            ORDER BY t.id DESC
            LIMIT ?
        """, (limite,)).fetchall()
        return [dict(f) for f in filas]
    finally:
        conn.close()


def obtener_torneo(torneo_id: int) -> dict | None:
    """Retorna un torneo con sus participantes y premios."""
    conn = get_connection()
    try:
        t = conn.execute("""
            SELECT t.*, u.usuario AS cajero
            FROM torneos t
            LEFT JOIN usuarios u ON t.usuario_id = u.id
            WHERE t.id = ?
        """, (torneo_id,)).fetchone()
        if not t:
            return None
        d = dict(t)
        d["participantes"] = [dict(p) for p in conn.execute("""
            SELECT tp.*, cl.nombre AS cliente_nombre
            FROM torneo_participantes tp
            LEFT JOIN clientes cl ON tp.cliente_id = cl.id
            WHERE tp.torneo_id = ? ORDER BY tp.id
        """, (torneo_id,)).fetchall()]
        d["premios"] = [dict(p) for p in conn.execute(
            "SELECT * FROM torneo_premios WHERE torneo_id = ? ORDER BY id",
            (torneo_id,)).fetchall()]
        return d
    finally:
        conn.close()


def resumen_torneos_periodo(fecha_inicio: str, fecha_fin: str) -> dict:
    """Totales de torneos en un rango de fechas (YYYY-MM-DD)."""
    conn = get_connection()
    try:
        r = conn.execute("""
            SELECT COUNT(*)                    AS num_torneos,
                   COALESCE(SUM(recaudado), 0) AS recaudado,
                   COALESCE(SUM(costo_premios), 0) AS costo_premios,
                   COALESCE(SUM(ganancia), 0)  AS ganancia
            FROM torneos
            WHERE date(fecha) BETWEEN ? AND ?
        """, (fecha_inicio, fecha_fin)).fetchone()
        return dict(r)
    finally:
        conn.close()
