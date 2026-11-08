"""
pos_api/servicios/caja.py — Turnos de caja: apertura, movimientos y cierre.

Nada guarda totales: el esperado de cada caja y su desglose salen de las
vistas v_sesion_cajas y v_flujos_caja (0019), y las reglas (un solo turno
abierto, turno cerrado inmutable, contado de billetes = denominaciones) las
hace cumplir la base.
"""
from decimal import Decimal

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado
from pos_api.seguridad import Usuario


def _pesos(monto) -> str:
    return "$" + f"{Decimal(monto):,.0f}".replace(",", ".")


def _id_turno_abierto(conn):
    fila = conn.execute("SELECT id FROM sesiones_caja WHERE cerrada_en IS NULL").fetchone()
    return fila["id"] if fila else None


# ── Lectura ─────────────────────────────────────────────────────────────────

def detalle_turno(conn, sesion_id) -> dict:
    """El turno con cada caja (base, esperado, contado, diferencias y el
    desglose del esperado por concepto), sus movimientos, el resumen de ventas
    y, si ya cerró, el conteo de billetes y monedas."""
    turno = conn.execute(
        """SELECT s.id, s.numero, s.abierta_en, s.cerrada_en, s.notas,
                  ua.usuario AS abierta_por, uc.usuario AS cerrada_por
             FROM sesiones_caja s
             JOIN usuarios ua ON ua.id = s.abierta_por
             LEFT JOIN usuarios uc ON uc.id = s.cerrada_por
            WHERE s.id = %s""",
        (sesion_id,),
    ).fetchone()
    if turno is None:
        raise NoEncontrado("El turno de caja no existe.")

    flujos: dict = {}
    for f in conn.execute(
            "SELECT caja_id, concepto, sum(monto) AS monto FROM v_flujos_caja WHERE sesion_id = %s GROUP BY 1, 2",
            (sesion_id,)):
        flujos.setdefault(f["caja_id"], {})[f["concepto"]] = f["monto"]
    turno["cajas"] = conn.execute(
        """SELECT vs.caja_id, vs.caja, c.usa_denominaciones, vs.base, vs.esperado, vs.contado,
                  vs.diferencia, vs.diferencia_apertura
             FROM v_sesion_cajas vs JOIN cajas c ON c.id = vs.caja_id
            WHERE vs.sesion_id = %s
            ORDER BY c.usa_denominaciones DESC, c.nombre""",
        (sesion_id,),
    ).fetchall()
    for caja in turno["cajas"]:
        caja["flujos"] = flujos.get(caja["caja_id"], {})

    turno["ventas"] = conn.execute(
        """SELECT count(*) AS cantidad, COALESCE(sum(total), 0) AS total, COALESCE(sum(fiado), 0) AS fiado
             FROM v_ventas WHERE sesion_id = %s""",
        (sesion_id,),
    ).fetchone()
    turno["movimientos"] = conn.execute(
        """SELECT m.id, m.tipo, m.caja_origen_id, co.nombre AS caja_origen, m.caja_destino_id,
                  cd.nombre AS caja_destino, m.monto, m.motivo, u.usuario, m.creado_en
             FROM movimientos_caja m
             JOIN usuarios u ON u.id = m.usuario_id
             LEFT JOIN cajas co ON co.id = m.caja_origen_id
             LEFT JOIN cajas cd ON cd.id = m.caja_destino_id
            WHERE m.sesion_id = %s
            ORDER BY m.creado_en, m.id""",
        (sesion_id,),
    ).fetchall()
    turno["conteo"] = conn.execute(
        """SELECT d.valor, d.tipo, cd.cantidad
             FROM conteo_denominaciones cd JOIN denominaciones d ON d.id = cd.denominacion_id
            WHERE cd.sesion_id = %s
            ORDER BY d.valor DESC""",
        (sesion_id,),
    ).fetchall()
    return turno


def turno_actual(conn) -> dict:
    """{"turno": detalle del turno abierto} o, sin turno, {"turno": None,
    "cajas": las cajas activas para abrir, con lo que se contó al cerrar el
    turno anterior (la base que debería declararse)}."""
    sesion_id = _id_turno_abierto(conn)
    if sesion_id is not None:
        return {"turno": detalle_turno(conn, sesion_id)}
    cajas = conn.execute(
        """SELECT c.id, c.nombre, c.usa_denominaciones,
                  (SELECT sc.contado
                     FROM sesion_cajas sc JOIN sesiones_caja s ON s.id = sc.sesion_id
                    WHERE sc.caja_id = c.id AND s.cerrada_en IS NOT NULL
                    ORDER BY s.numero DESC LIMIT 1) AS contado_anterior
             FROM cajas c
            WHERE c.activo
            ORDER BY c.usa_denominaciones DESC, c.nombre"""
    ).fetchall()
    return {"turno": None, "cajas": cajas}


def denominaciones(conn) -> list[dict]:
    return conn.execute(
        "SELECT id, valor, tipo FROM denominaciones WHERE activa ORDER BY valor DESC"
    ).fetchall()


def historial(conn, *, desde=None, hasta=None, limite: int = 200) -> list[dict]:
    """Turnos del más nuevo al más viejo, con lo vendido y la diferencia de
    cada caja. desde/hasta filtran por el día de apertura."""
    return conn.execute(
        """SELECT s.id, s.numero, s.abierta_en, s.cerrada_en,
                  ua.usuario AS abierta_por, uc.usuario AS cerrada_por,
                  (SELECT COALESCE(sum(total), 0) FROM v_ventas WHERE sesion_id = s.id) AS ventas,
                  (SELECT json_agg(json_build_object('caja', vs.caja, 'diferencia', vs.diferencia)
                                   ORDER BY c.usa_denominaciones DESC, c.nombre)
                     FROM v_sesion_cajas vs JOIN cajas c ON c.id = vs.caja_id
                    WHERE vs.sesion_id = s.id) AS cajas
             FROM sesiones_caja s
             JOIN usuarios ua ON ua.id = s.abierta_por
             LEFT JOIN usuarios uc ON uc.id = s.cerrada_por
            WHERE (%(desde)s::date IS NULL OR s.abierta_en >= %(desde)s::date)
              AND (%(hasta)s::date IS NULL OR s.abierta_en < %(hasta)s::date + 1)
            ORDER BY s.numero DESC
            LIMIT %(limite)s""",
        {"desde": desde, "hasta": hasta, "limite": limite},
    ).fetchall()


# ── Apertura ────────────────────────────────────────────────────────────────

def abrir_turno(conn, actor: Usuario, bases: dict, notas: str | None) -> dict:
    """bases: {caja_id: base declarada} con TODAS las cajas activas (la plata
    solo puede moverse en cajas del turno)."""
    activas = {c["id"]: c["nombre"] for c in conn.execute("SELECT id, nombre FROM cajas WHERE activo FOR SHARE")}
    if not activas:
        raise ErrorNegocio("No hay cajas activas: crea una en Configuración.")
    sobran = set(bases) - set(activas)
    if sobran:
        raise ErrorNegocio("Una de las cajas indicadas no existe o está desactivada.")
    faltan = [nombre for id_, nombre in activas.items() if id_ not in bases]
    if faltan:
        raise ErrorNegocio(f"Falta la base de: {', '.join(sorted(faltan))}.")

    turno = conn.execute(
        "INSERT INTO sesiones_caja (abierta_por, notas) VALUES (%s, %s) RETURNING id, numero",
        (actor.id, notas),
    ).fetchone()
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO sesion_cajas (sesion_id, caja_id, base) VALUES (%s, %s, %s)",
            [(turno["id"], caja_id, base) for caja_id, base in bases.items()],
        )
    detalle = ", ".join(f"{activas[c]} {_pesos(b)}" for c, b in sorted(bases.items(), key=lambda x: activas[x[0]]))
    auditar(conn, actor.id, "caja", f"Abrió el turno #{turno['numero']} (bases: {detalle})",
            "sesiones_caja", turno["id"])
    return detalle_turno(conn, turno["id"])


# ── Movimientos ─────────────────────────────────────────────────────────────

def registrar_movimiento(conn, actor: Usuario, sesion_id, tipo: str, caja_origen_id, caja_destino_id,
                         monto, motivo: str) -> dict:
    """Retiro (sale de una caja), ingreso (entra a una caja) o traslado (de una
    caja a otra, ej. consignar el efectivo). Va al turno que el cajero tiene en
    pantalla: si mientras tanto se cerró, falla en vez de caer en el siguiente.
    Un error se corrige con el movimiento contrario."""
    turno = conn.execute("SELECT numero, cerrada_en FROM sesiones_caja WHERE id = %s", (sesion_id,)).fetchone()
    if turno is None:
        raise NoEncontrado("El turno de caja no existe.")
    if turno["cerrada_en"] is not None:
        raise ErrorNegocio(f"El turno #{turno['numero']} ya está cerrado.")
    indicadas = [c for c in (caja_origen_id, caja_destino_id) if c is not None]
    nombres = {c["id"]: c["nombre"] for c in conn.execute(
        "SELECT id, nombre FROM cajas WHERE id = ANY(%s)", (indicadas,))}
    if len(nombres) != len(set(indicadas)):
        raise NoEncontrado("La caja indicada no existe.")
    # El trigger vuelve a revisar el turno con bloqueo (por si se cierra ahora).
    fila = conn.execute(
        """INSERT INTO movimientos_caja (sesion_id, tipo, caja_origen_id, caja_destino_id, monto, motivo, usuario_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (sesion_id, tipo, caja_origen_id, caja_destino_id, monto, motivo, actor.id),
    ).fetchone()
    auditar(conn, actor.id, "caja",
            f"Registró un {tipo} de {_pesos(monto)} ({' → '.join(nombres[c] for c in indicadas)}): {motivo}",
            "movimientos_caja", fila["id"])
    return detalle_turno(conn, sesion_id)


# ── Cierre ──────────────────────────────────────────────────────────────────

def cerrar_turno(conn, actor: Usuario, sesion_id, contados: dict, conteo: dict, notas: str | None) -> dict:
    """contados: {caja_id: contado} de las cajas que no se cuentan en billetes;
    conteo: {denominacion_id: cantidad} de la caja que sí (su contado es la
    suma). Se cierra el turno que el cajero tiene en pantalla: si mientras
    tanto otro lo cerró, falla en vez de cerrar uno nuevo."""
    # FOR UPDATE: espera a las ventas en curso (que toman el turno FOR SHARE)
    # y, desde aquí, nada más entra al turno.
    turno = conn.execute(
        "SELECT numero, cerrada_en, notas FROM sesiones_caja WHERE id = %s FOR UPDATE", (sesion_id,)
    ).fetchone()
    if turno is None:
        raise NoEncontrado("El turno de caja no existe.")
    if turno["cerrada_en"] is not None:
        raise ErrorNegocio(f"El turno #{turno['numero']} ya está cerrado.")

    cajas = conn.execute(
        """SELECT sc.caja_id, c.nombre, c.usa_denominaciones
             FROM sesion_cajas sc JOIN cajas c ON c.id = sc.caja_id
            WHERE sc.sesion_id = %s""",
        (sesion_id,),
    ).fetchall()
    del_turno = {c["caja_id"]: c for c in cajas}
    for caja_id in contados:
        caja = del_turno.get(caja_id)
        if caja is None:
            raise ErrorNegocio("Una de las cajas indicadas no está en este turno.")
        if caja["usa_denominaciones"]:
            raise ErrorNegocio(f"La caja {caja['nombre']} se cuenta en billetes y monedas.")

    conteo = {d: n for d, n in conteo.items() if n > 0}
    con_billetes = next((c for c in cajas if c["usa_denominaciones"]), None)
    if conteo and con_billetes is None:
        raise ErrorNegocio("Ninguna caja de este turno se cuenta en billetes y monedas.")
    valores = {d["id"]: d["valor"] for d in conn.execute(
        "SELECT id, valor FROM denominaciones WHERE id = ANY(%s)", (list(conteo),))}
    if len(valores) != len(conteo):
        raise ErrorNegocio("Una de las denominaciones indicadas no existe.")

    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO conteo_denominaciones (sesion_id, denominacion_id, cantidad) VALUES (%s, %s, %s)",
            [(sesion_id, d, n) for d, n in conteo.items()],
        )
        filas = []
        for caja in cajas:
            if caja["usa_denominaciones"]:
                contado = sum((Decimal(valores[d]) * n for d, n in conteo.items()), Decimal(0))
            elif caja["caja_id"] in contados:
                contado = contados[caja["caja_id"]]
            else:
                raise ErrorNegocio(f"Falta el conteo de la caja {caja['nombre']}.")
            filas.append((contado, sesion_id, caja["caja_id"]))
        cur.executemany("UPDATE sesion_cajas SET contado = %s WHERE sesion_id = %s AND caja_id = %s", filas)

    notas_finales = "\n".join(n for n in (turno["notas"], notas) if n) or None
    conn.execute(
        "UPDATE sesiones_caja SET cerrada_por = %s, cerrada_en = now(), notas = %s WHERE id = %s",
        (actor.id, notas_finales, sesion_id),
    )

    detalle = detalle_turno(conn, sesion_id)
    resumen = ", ".join(f"{c['caja']} {_describir_diferencia(c['diferencia'])}" for c in detalle["cajas"])
    auditar(conn, actor.id, "caja", f"Cerró el turno #{turno['numero']}: {resumen}", "sesiones_caja", sesion_id)
    return detalle


def _describir_diferencia(diferencia) -> str:
    if diferencia == 0:
        return "cuadra"
    return f"{'sobran' if diferencia > 0 else 'faltan'} {_pesos(abs(diferencia))}"
