"""
pos_api/servicios/egresos.py — Toda salida de plata: gastos y pagos de compras.

Un egreso es un gasto (con categoría; nómina es un gasto pagado a una
persona) o el pago de una compra. Se paga con plata de las cajas del turno
(pagos por método) y/o con un cruce de cuentas: si el beneficiario debe
fiado, se le descuenta de lo que el negocio le paga (un abono a su deuda).
El monto no se guarda: es pagos + cruce (v_egresos).

Un egreso no se edita: se anula. La plata vuelve a sus cajas en el turno de
la anulación y el cruce deja de contar (la deuda reaparece).

Permisos (los revisa el router): un gasto lo registra cualquier usuario con
sesión; pagar una compra exige compras.registrar; un cruce de cuentas exige
creditos.condonar (baja una deuda sin que entre plata, como condonar); anular
exige gastos.anular. Sin reportes.ver solo se ven los egresos del turno abierto.
"""
from datetime import date
from decimal import Decimal

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado
from pos_api.seguridad import Usuario
from pos_api.servicios.caja import exigir_turno_abierto
from pos_api.servicios.comun import pesos
from pos_api.servicios.credito import aplicar_abono
from pos_api.servicios.ventas import nombres_metodos

_EGRESO = """
    SELECT ve.id, ve.creado_en, ve.concepto, ve.notas, ve.monto, ve.pagado, ve.cruzado, ve.anulado,
           ve.sesion_id, s.numero AS turno, u.usuario,
           CASE WHEN ve.compra_id IS NOT NULL THEN 'compra' ELSE 'gasto' END AS tipo,
           ve.categoria_gasto_id, cg.nombre AS categoria, ve.compra_id, co.numero AS compra_numero,
           COALESCE(ve.tercero_id, co.proveedor_id) AS beneficiario_id, b.nombre AS beneficiario,
           (SELECT string_agg(mp.nombre, ', ' ORDER BY pe.id) FROM pagos_egreso pe
              JOIN metodos_pago mp ON mp.id = pe.metodo_pago_id WHERE pe.egreso_id = ve.id) AS metodos,
           an.motivo AS motivo_anulacion, an.creado_en AS anulado_en, ua.usuario AS anulado_por,
           sa.numero AS turno_anulacion
      FROM v_egresos ve
      JOIN sesiones_caja s ON s.id = ve.sesion_id
      JOIN usuarios u ON u.id = ve.usuario_id
      LEFT JOIN categorias_gasto cg ON cg.id = ve.categoria_gasto_id
      LEFT JOIN compras co ON co.id = ve.compra_id
      LEFT JOIN terceros b ON b.id = COALESCE(ve.tercero_id, co.proveedor_id)
      LEFT JOIN anulaciones_egreso an ON an.egreso_id = ve.id
      LEFT JOIN usuarios ua ON ua.id = an.usuario_id
      LEFT JOIN sesiones_caja sa ON sa.id = an.sesion_id
"""


def listar_egresos(conn, *, desde: date | None = None, hasta: date | None = None, tipo: str | None = None,
                   categoria_gasto_id=None, sesion_id=None, limite: int = 300) -> list[dict]:
    """Del más nuevo al más viejo; desde/hasta son días completos. sesion_id
    deja solo los de ese turno."""
    return conn.execute(
        _EGRESO + """
         WHERE (%(desde)s::date IS NULL OR ve.creado_en >= %(desde)s::date)
           AND (%(hasta)s::date IS NULL OR ve.creado_en < %(hasta)s::date + 1)
           AND (%(tipo)s::text IS NULL OR (%(tipo)s = 'compra') = (ve.compra_id IS NOT NULL))
           AND (%(categoria)s::uuid IS NULL OR ve.categoria_gasto_id = %(categoria)s)
           AND (%(sesion)s::uuid IS NULL OR ve.sesion_id = %(sesion)s)
         ORDER BY ve.creado_en DESC, ve.id DESC
         LIMIT %(limite)s""",
        {"desde": desde, "hasta": hasta, "tipo": tipo, "categoria": categoria_gasto_id, "sesion": sesion_id,
         "limite": limite},
    ).fetchall()


def detalle_egreso(conn, egreso_id) -> dict:
    egreso = conn.execute(_EGRESO + " WHERE ve.id = %s", (egreso_id,)).fetchone()
    if egreso is None:
        raise NoEncontrado("El egreso no existe.")
    egreso["pagos"] = conn.execute(
        """SELECT mp.nombre AS metodo, c.nombre AS caja, pe.monto
             FROM pagos_egreso pe JOIN metodos_pago mp ON mp.id = pe.metodo_pago_id JOIN cajas c ON c.id = mp.caja_id
            WHERE pe.egreso_id = %s ORDER BY pe.id""",
        (egreso_id,),
    ).fetchall()
    return egreso


def registrar_egreso(conn, actor: Usuario, sesion_id, *, concepto: str, compra_id=None, categoria_gasto_id=None,
                     tercero_id=None, pagos: list[dict] = (), cruce: Decimal = Decimal(0),
                     notas: str | None = None) -> dict:
    """Un gasto (categoria_gasto_id, tercero_id opcional) o el pago de una
    compra (compra_id; el beneficiario es su proveedor). pagos = [{metodo_pago_id,
    monto}] salen de las cajas del turno; cruce es lo que se descuenta de la
    deuda de fiado del beneficiario."""
    numero_turno = exigir_turno_abierto(conn, sesion_id)
    if (compra_id is None) == (categoria_gasto_id is None):
        raise ErrorNegocio("Un egreso es un gasto con categoría o el pago de una compra.")
    pagos = list(pagos)
    metodos = nombres_metodos(conn, [p["metodo_pago_id"] for p in pagos]) if pagos else {}
    total = sum((p["monto"] for p in pagos), Decimal(0)) + cruce
    if total <= 0:
        raise ErrorNegocio("Indica cuánto se paga.")

    if compra_id is not None:
        compra = conn.execute(
            """SELECT co.numero, co.proveedor_id, t.nombre FROM compras co JOIN terceros t ON t.id = co.proveedor_id
                WHERE co.id = %s FOR UPDATE OF co""", (compra_id,)).fetchone()
        if compra is None:
            raise NoEncontrado("La compra no existe.")
        pendiente = conn.execute("SELECT pendiente FROM v_compras WHERE id = %s", (compra_id,)).fetchone()["pendiente"]
        if pendiente <= 0:
            raise ErrorNegocio(f"La compra #{compra['numero']} ya está pagada.")
        if total > pendiente:
            raise ErrorNegocio(f"A la compra #{compra['numero']} le quedan {pesos(pendiente)} por pagar "
                               f"y se están pagando {pesos(total)}.")
        beneficiario, nombre = compra["proveedor_id"], compra["nombre"]
        tercero_id = None
    else:
        categoria = conn.execute("SELECT nombre, activa FROM categorias_gasto WHERE id = %s",
                                 (categoria_gasto_id,)).fetchone()
        if categoria is None:
            raise NoEncontrado("La categoría de gasto no existe.")
        if not categoria["activa"]:
            raise ErrorNegocio(f"La categoría {categoria['nombre']} está desactivada.")
        nombre = None
        if tercero_id is not None:
            fila = conn.execute("SELECT nombre FROM terceros WHERE id = %s", (tercero_id,)).fetchone()
            if fila is None:
                raise NoEncontrado("La persona a la que se le paga no existe.")
            nombre = fila["nombre"]
        beneficiario = tercero_id
    if cruce > 0:
        if beneficiario is None:
            raise ErrorNegocio("Para cruzar cuentas indica a quién se le paga.")
        if conn.execute("SELECT 1 FROM clientes WHERE tercero_id = %s", (beneficiario,)).fetchone() is None:
            raise ErrorNegocio(f"{nombre} no es cliente: no tiene fiado contra el cual cruzar.")

    egreso = conn.execute(
        """INSERT INTO egresos (sesion_id, usuario_id, compra_id, categoria_gasto_id, tercero_id, concepto, notas)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (sesion_id, actor.id, compra_id, categoria_gasto_id, tercero_id, concepto, notas),
    ).fetchone()
    if pagos:
        conn.cursor().executemany(
            "INSERT INTO pagos_egreso (egreso_id, metodo_pago_id, monto) VALUES (%s, %s, %s)",
            [(egreso["id"], p["metodo_pago_id"], p["monto"]) for p in pagos],
        )
    partes = [f"{metodos[p['metodo_pago_id']]} {pesos(p['monto'])}" for p in pagos]
    if cruce > 0:
        abono = aplicar_abono(conn, actor, beneficiario, cruce, egreso_id=egreso["id"], notas=f"Cruce: {concepto}")
        partes.append(f"cruce {pesos(cruce)} contra su fiado (queda debiendo {pesos(abono['deuda'] - cruce)})")

    if compra_id is not None:
        texto = f"Pagó {pesos(total)} de la compra #{compra['numero']} a {nombre}"
        accion = "compra"
    else:
        texto = f"Gasto de {pesos(total)} ({categoria['nombre']}): {concepto}" + (f", a {nombre}" if nombre else "")
        accion = "gasto"
    auditar(conn, actor.id, accion, f"{texto} en el turno #{numero_turno} ({', '.join(partes)})",
            "egresos", egreso["id"])
    return detalle_egreso(conn, egreso["id"])


def anular_egreso(conn, actor: Usuario, egreso_id, sesion_id, motivo: str) -> dict:
    """La plata vuelve a sus cajas en el turno indicado (el que está abierto);
    el turno original no se toca. Un cruce deja de contar: la deuda reaparece."""
    numero_turno = exigir_turno_abierto(conn, sesion_id)
    egreso = conn.execute("SELECT id FROM egresos WHERE id = %s FOR UPDATE", (egreso_id,)).fetchone()
    if egreso is None:
        raise NoEncontrado("El egreso no existe.")
    actual = detalle_egreso(conn, egreso_id)
    if actual["anulado"]:
        raise ErrorNegocio("Ese egreso ya está anulado.")
    conn.execute(
        "INSERT INTO anulaciones_egreso (egreso_id, sesion_id, usuario_id, motivo) VALUES (%s, %s, %s, %s)",
        (egreso_id, sesion_id, actor.id, motivo),
    )
    que = f"el pago de la compra #{actual['compra_numero']}" if actual["compra_id"] else f"el gasto «{actual['concepto']}»"
    devuelto = f"; vuelven {pesos(actual['pagado'])} a caja en el turno #{numero_turno}" if actual["pagado"] else ""
    cruce = f"; el cruce de {pesos(actual['cruzado'])} deja de contar" if actual["cruzado"] else ""
    auditar(conn, actor.id, "compra" if actual["compra_id"] else "gasto",
            f"Anuló {que} por {pesos(actual['monto'])}{devuelto}{cruce}: {motivo}", "egresos", egreso_id)
    return detalle_egreso(conn, egreso_id)
