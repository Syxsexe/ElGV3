"""
pos_api/servicios/credito.py — Fiado: saldos, cargos, abonos y condonaciones.

Lo que se fía son cargos (de una venta, o manuales como un saldo inicial);
lo que se paga son abonos, cada uno aplicado completo a cargos concretos del
mismo cliente; lo que se perdona son condonaciones de un cargo. Saldo,
pendiente y vencido se calculan en las vistas v_cargos_credito y
v_saldos_clientes, y la base impide pagar o condonar de más.

Permisos: ver saldos y recibir abonos lo hace cualquier usuario con sesión
(el cajero cobra el fiado); un cargo manual exige clientes.editar y condonar
exige creditos.condonar.
"""
from datetime import date
from decimal import Decimal

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado
from pos_api.seguridad import Usuario
from pos_api.servicios.caja import exigir_turno_abierto
from pos_api.servicios.comun import busqueda_tercero, pesos
from pos_api.servicios.terceros import con_dv
from pos_api.servicios.ventas import nombres_metodos

# Orden en que un abono paga los cargos si no se elige: el que vence primero.
ORDEN_PAGO = "vence_en, creado_en, id"
# Cuántos cargos pagados, abonos y condonaciones trae el detalle (los más nuevos).
HISTORIAL = 100

_SALDOS = """
    SELECT s.cliente_id, s.nombre, ti.codigo AS tipo_identificacion, t.numero_identificacion, t.telefono,
           cl.activo, s.limite_credito, s.dias_credito, s.saldo, s.disponible, s.cargos_vencidos,
           s.proximo_vencimiento,
           COALESCE((SELECT sum(vc.pendiente) FROM v_cargos_credito vc
                      WHERE vc.cliente_id = s.cliente_id AND vc.vencido), 0) AS vencido
      FROM v_saldos_clientes s
      JOIN clientes cl ON cl.tercero_id = s.cliente_id
      JOIN terceros t ON t.id = s.cliente_id
      LEFT JOIN tipos_identificacion ti ON ti.id = t.tipo_identificacion_id
"""


def _describir_cargo(cargo: dict) -> str:
    origen = f"venta #{cargo['venta_numero']}" if cargo.get("venta_numero") else cargo.get("notas") or "cargo manual"
    return f"{pesos(cargo['monto'])} ({origen})"


# ── Consultas ───────────────────────────────────────────────────────────────

def listar_saldos(conn, texto: str | None = None, limite: int = 200) -> list[dict]:
    """Sin texto: los clientes que deben algo, primero los que tienen deuda
    vencida y luego los que más deben. Con texto: cualquier cliente que
    coincida por nombre o documento (para abonarle o cargarle aunque no deba)."""
    buscar, params = busqueda_tercero(texto, nombre="s.nombre")
    filas = conn.execute(
        _SALDOS + f"""
         WHERE CASE WHEN %(patron)s::text IS NULL THEN s.saldo > 0 ELSE {buscar} END
         ORDER BY (s.cargos_vencidos > 0) DESC, s.saldo DESC, s.nombre
         LIMIT %(limite)s""",
        {"limite": limite, **params},
    ).fetchall()
    return [con_dv(f) for f in filas]


def resumen_cartera(conn) -> dict:
    return conn.execute(
        """SELECT COALESCE(sum(pendiente), 0) AS total,
                  COALESCE(sum(pendiente) FILTER (WHERE vencido), 0) AS vencido,
                  count(DISTINCT cliente_id) FILTER (WHERE pendiente > 0) AS clientes
             FROM v_cargos_credito"""
    ).fetchone()


def detalle_credito(conn, cliente_id) -> dict:
    """El saldo del cliente con sus cargos (pendientes primero, en el orden en
    que se pagan), sus abonos y sus condonaciones."""
    cliente = conn.execute(_SALDOS + " WHERE s.cliente_id = %s", (cliente_id,)).fetchone()
    if cliente is None:
        raise NoEncontrado("El cliente no existe.")
    detalle = {"cliente": con_dv(cliente)}
    # Los pendientes van todos (el abono los reparte) en el orden en que se
    # pagan; de los ya pagados, solo los más recientes, con el total aparte.
    cargos = """SELECT * FROM (
                    SELECT vc.id, vc.creado_en, vc.vence_en, vc.monto, vc.abonado, vc.condonado, vc.pendiente,
                           vc.vencido, vc.notas, vc.venta_id, v.numero AS venta_numero
                      FROM v_cargos_credito vc
                      LEFT JOIN ventas v ON v.id = vc.venta_id
                     WHERE vc.cliente_id = %s) c"""
    detalle["cargos"] = (
        conn.execute(cargos + f" WHERE pendiente > 0 ORDER BY {ORDEN_PAGO}", (cliente_id,)).fetchall()
        + conn.execute(cargos + " WHERE pendiente = 0 ORDER BY creado_en DESC, id DESC LIMIT %s",
                       (cliente_id, HISTORIAL)).fetchall())
    detalle["totales"] = conn.execute(
        """SELECT (SELECT count(*) FROM v_cargos_credito WHERE cliente_id = %(c)s AND pendiente = 0) AS cargos_pagados,
                  (SELECT count(*) FROM abonos_credito WHERE cliente_id = %(c)s) AS abonos,
                  (SELECT count(*) FROM condonaciones_credito cd JOIN cargos_credito c ON c.id = cd.cargo_id
                    WHERE c.cliente_id = %(c)s) AS condonaciones""",
        {"c": cliente_id},
    ).fetchone()
    detalle["abonos"] = conn.execute(
        """SELECT a.id, a.creado_en, a.monto, a.notas, mp.nombre AS metodo, s.numero AS turno, u.usuario,
                  a.egreso_id IS NOT NULL AS cruce, abono_vigente(a.id) AS vigente,
                  (SELECT count(*) FROM abono_aplicaciones aa WHERE aa.abono_id = a.id) AS cargos
             FROM abonos_credito a
             JOIN usuarios u ON u.id = a.usuario_id
             LEFT JOIN metodos_pago mp ON mp.id = a.metodo_pago_id
             LEFT JOIN sesiones_caja s ON s.id = a.sesion_id
            WHERE a.cliente_id = %s
            ORDER BY a.creado_en DESC, a.id DESC
            LIMIT %s""",
        (cliente_id, HISTORIAL),
    ).fetchall()
    detalle["condonaciones"] = conn.execute(
        """SELECT cd.id, cd.creado_en, cd.monto, cd.motivo, cd.cargo_id, u.usuario AS autorizada_por
             FROM condonaciones_credito cd
             JOIN cargos_credito c ON c.id = cd.cargo_id
             JOIN usuarios u ON u.id = cd.autorizada_por
            WHERE c.cliente_id = %s
            ORDER BY cd.creado_en DESC, cd.id DESC
            LIMIT %s""",
        (cliente_id, HISTORIAL),
    ).fetchall()
    return detalle


# ── Escritura ───────────────────────────────────────────────────────────────

def _tomar_cliente(conn, cliente_id) -> dict:
    """Bloquea al cliente: dos abonos (o un abono y una venta fiada) del mismo
    cliente se esperan, y el segundo ve lo que hizo el primero."""
    fila = conn.execute(
        """SELECT t.nombre, cl.dias_credito FROM clientes cl JOIN terceros t ON t.id = cl.tercero_id
            WHERE cl.tercero_id = %s FOR UPDATE OF cl""",
        (cliente_id,),
    ).fetchone()
    if fila is None:
        raise NoEncontrado("El cliente no existe.")
    return fila


def registrar_cargo(conn, actor: Usuario, cliente_id, monto: Decimal, notas: str, vence_en: date | None) -> dict:
    """Cargo sin venta: un saldo que venía de antes, un préstamo… Las notas
    dicen de dónde sale. Sin vence_en, vence según los días de crédito del
    cliente. No revisa el cupo: lo registra quien administra los clientes."""
    cliente = _tomar_cliente(conn, cliente_id)
    fila = conn.execute(
        """INSERT INTO cargos_credito (cliente_id, monto, vence_en, notas)
           VALUES (%s, %s, COALESCE(%s, current_date + %s), %s) RETURNING id""",
        (cliente_id, monto, vence_en, cliente["dias_credito"], notas),
    ).fetchone()
    auditar(conn, actor.id, "credito", f"Cargó {pesos(monto)} a {cliente['nombre']}: {notas}",
            "cargos_credito", fila["id"])
    return detalle_credito(conn, cliente_id)


def aplicar_abono(conn, actor: Usuario, cliente_id, monto: Decimal, aplicaciones: list[dict] | None = None, *,
                  sesion_id=None, metodo_pago_id=None, egreso_id=None, notas: str | None = None) -> dict:
    """Inserta un abono y lo reparte entre cargos pendientes del cliente: con
    plata (sesion_id + metodo_pago_id) o con un cruce de cuentas (egreso_id:
    se le descuenta la deuda de lo que el negocio le paga). aplicaciones =
    [{cargo_id, monto}] dice qué cargos paga; sin ellas paga primero los que
    vencen antes. No puede superar lo que debe. Retorna {id, nombre, cargos,
    deuda} (deuda = lo que debía antes del abono)."""
    cliente = _tomar_cliente(conn, cliente_id)
    pendientes = {c["id"]: c["pendiente"] for c in conn.execute(
        f"SELECT id, pendiente FROM v_cargos_credito WHERE cliente_id = %s AND pendiente > 0 ORDER BY {ORDEN_PAGO}",
        (cliente_id,))}
    deuda = sum(pendientes.values(), Decimal(0))
    if deuda == 0:
        raise ErrorNegocio(f"{cliente['nombre']} no debe nada.")
    if monto > deuda:
        raise ErrorNegocio(f"El abono ({pesos(monto)}) supera lo que debe {cliente['nombre']} ({pesos(deuda)}).")

    if aplicaciones:
        repartido = {}
        for a in aplicaciones:
            if a["cargo_id"] in repartido:
                raise ErrorNegocio("Un cargo aparece dos veces en el abono: junta los montos.")
            if a["cargo_id"] not in pendientes:
                raise ErrorNegocio("Uno de los cargos elegidos no es de este cliente o ya está pagado.")
            if a["monto"] > pendientes[a["cargo_id"]]:
                raise ErrorNegocio(f"A un cargo se le aplicarían {pesos(a['monto'])} y solo le quedan "
                                   f"{pesos(pendientes[a['cargo_id']])} por pagar.")
            repartido[a["cargo_id"]] = a["monto"]
        if sum(repartido.values(), Decimal(0)) != monto:
            raise ErrorNegocio(f"Lo repartido en los cargos ({pesos(sum(repartido.values(), Decimal(0)))}) "
                               f"no es igual al abono ({pesos(monto)}).")
    else:
        repartido, resto = {}, monto
        for cargo_id, pendiente in pendientes.items():  # ya vienen en ORDEN_PAGO
            if resto == 0:
                break
            repartido[cargo_id] = min(pendiente, resto)
            resto -= repartido[cargo_id]

    abono = conn.execute(
        """INSERT INTO abonos_credito (cliente_id, sesion_id, metodo_pago_id, egreso_id, usuario_id, monto, notas)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (cliente_id, sesion_id, metodo_pago_id, egreso_id, actor.id, monto, notas),
    ).fetchone()
    conn.cursor().executemany(
        "INSERT INTO abono_aplicaciones (abono_id, cargo_id, monto) VALUES (%s, %s, %s)",
        [(abono["id"], cargo_id, m) for cargo_id, m in repartido.items()],
    )
    return {"id": abono["id"], "nombre": cliente["nombre"], "cargos": len(repartido), "deuda": deuda}


def registrar_abono(conn, actor: Usuario, cliente_id, sesion_id, metodo_pago_id, monto: Decimal,
                    aplicaciones: list[dict] | None = None, notas: str | None = None) -> dict:
    """Plata que el cliente paga, en el turno que el cajero tiene en pantalla."""
    numero_turno = exigir_turno_abierto(conn, sesion_id)
    metodo = nombres_metodos(conn, [metodo_pago_id])[metodo_pago_id]
    abono = aplicar_abono(conn, actor, cliente_id, monto, aplicaciones,
                          sesion_id=sesion_id, metodo_pago_id=metodo_pago_id, notas=notas)
    auditar(conn, actor.id, "credito",
            f"Abono de {pesos(monto)} de {abono['nombre']} ({metodo}) en el turno #{numero_turno}, "
            f"aplicado a {abono['cargos']} cargo(s); queda debiendo {pesos(abono['deuda'] - monto)}",
            "abonos_credito", abono["id"])
    return detalle_credito(conn, cliente_id)


def condonar(conn, actor: Usuario, cargo_id, monto: Decimal, motivo: str) -> dict:
    """Perdona parte o todo lo pendiente de un cargo (o corrige uno mal hecho),
    sin pasar por caja."""
    fila = conn.execute("SELECT cliente_id FROM cargos_credito WHERE id = %s FOR UPDATE", (cargo_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("El cargo no existe.")
    cargo = conn.execute(
        """SELECT vc.monto, vc.pendiente, vc.notas, v.numero AS venta_numero, t.nombre
             FROM v_cargos_credito vc
             JOIN terceros t ON t.id = vc.cliente_id
             LEFT JOIN ventas v ON v.id = vc.venta_id
            WHERE vc.id = %s""",
        (cargo_id,),
    ).fetchone()
    if cargo["pendiente"] == 0:
        raise ErrorNegocio("Ese cargo ya está pagado: no hay nada que condonar.")
    if monto > cargo["pendiente"]:
        raise ErrorNegocio(f"Al cargo solo le quedan {pesos(cargo['pendiente'])} por pagar.")
    conn.execute(
        "INSERT INTO condonaciones_credito (cargo_id, monto, motivo, autorizada_por) VALUES (%s, %s, %s, %s)",
        (cargo_id, monto, motivo, actor.id),
    )
    auditar(conn, actor.id, "credito",
            f"Condonó {pesos(monto)} a {cargo['nombre']} del cargo de {_describir_cargo(cargo)}: {motivo}",
            "cargos_credito", cargo_id)
    return detalle_credito(conn, fila["cliente_id"])
