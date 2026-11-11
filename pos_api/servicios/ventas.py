"""
pos_api/servicios/ventas.py — Ventas: líneas, pagos y la parte fiada.

Una venta guarda la foto de cada línea (precio, costo e impuesto del momento)
y nunca se edita. Su total es Σ cantidad × precio − descuento, y se cubre con
pagos (plata real que entra a la caja del método) más lo fiado (un cargo al
cliente que vence según sus días de crédito). La base revisa el cuadre al
confirmar; aquí se revisa antes para dar un mensaje claro.

Va al turno que el cajero tiene en pantalla (sesion_id): si se cerró mientras
tanto, la venta falla en vez de caer en el turno siguiente.
"""
from decimal import ROUND_HALF_UP, Decimal

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado
from pos_api.seguridad import Usuario
from pos_api.servicios.caja import exigir_turno_abierto
from pos_api.servicios.comun import pesos

CENTAVO = Decimal("0.01")


def _redondear(monto: Decimal) -> Decimal:
    # Igual que round(numeric, 2) en Postgres: la mitad se aleja del cero.
    return monto.quantize(CENTAVO, rounding=ROUND_HALF_UP)


# ── Lectura ─────────────────────────────────────────────────────────────────

def detalle_venta(conn, venta_id) -> dict:
    venta = conn.execute(
        """SELECT v.id, v.numero, v.sesion_id, v.creada_en, v.subtotal, v.descuento, v.total, v.pagado,
                  v.fiado, v.metodo, v.notas, v.cliente_id, t.nombre AS cliente, u.usuario,
                  cu.id AS cuenta_id, cu.numero AS cuenta_numero, m.nombre AS mesa
             FROM v_ventas v
             JOIN usuarios u ON u.id = v.usuario_id
             LEFT JOIN terceros t ON t.id = v.cliente_id
             LEFT JOIN cuentas cu ON cu.venta_id = v.id
             LEFT JOIN mesas m ON m.id = cu.mesa_id
            WHERE v.id = %s""",
        (venta_id,),
    ).fetchone()
    if venta is None:
        raise NoEncontrado("La venta no existe.")
    venta["lineas"] = conn.execute(
        """SELECT d.articulo_id, a.nombre, d.cantidad, d.precio_unit, round(d.cantidad * d.precio_unit, 2) AS subtotal
             FROM detalle_venta d JOIN articulos a ON a.id = d.articulo_id
            WHERE d.venta_id = %s ORDER BY d.id""",
        (venta_id,),
    ).fetchall()
    venta["pagos"] = conn.execute(
        """SELECT mp.nombre AS metodo, pv.monto
             FROM pagos_venta pv JOIN metodos_pago mp ON mp.id = pv.metodo_pago_id
            WHERE pv.venta_id = %s ORDER BY pv.id""",
        (venta_id,),
    ).fetchall()
    return venta


def exigir_cliente(conn, cliente_id) -> None:
    if conn.execute("SELECT 1 FROM clientes WHERE tercero_id = %s", (cliente_id,)).fetchone() is None:
        raise NoEncontrado("El cliente no existe.")


def cupo_cliente(conn, cliente_id, bloquear: bool = False) -> dict:
    """Cupo de fiado del cliente: límite, saldo pendiente y lo disponible.
    Con bloquear=True deja tomada la fila del cliente: dos ventas fiadas al
    mismo cliente a la vez se esperan y la segunda ve el saldo de la primera."""
    fila = conn.execute(
        "SELECT activo FROM clientes WHERE tercero_id = %s" + (" FOR UPDATE" if bloquear else ""),
        (cliente_id,),
    ).fetchone()
    if fila is None:
        raise NoEncontrado("El cliente no existe.")
    cupo = conn.execute(
        """SELECT cliente_id, nombre, limite_credito, dias_credito, saldo, disponible, cargos_vencidos
             FROM v_saldos_clientes WHERE cliente_id = %s""",
        (cliente_id,),
    ).fetchone()
    cupo["activo"] = fila["activo"]
    return cupo


# ── Registro ────────────────────────────────────────────────────────────────

def _articulos(conn, ids: list, exigir_activos: bool) -> dict:
    filas = {a["id"]: a for a in conn.execute(
        "SELECT id, nombre, activo, precio_venta FROM articulos WHERE id = ANY(%s)", (ids,))}
    if len(filas) != len(set(ids)):
        raise NoEncontrado("Uno de los artículos no existe.")
    if exigir_activos:
        inactivos = sorted(a["nombre"] for a in filas.values() if not a["activo"])
        if inactivos:
            raise ErrorNegocio(f"Ya no se vende: {', '.join(inactivos)}.")
    return filas


def nombres_metodos(conn, ids: list) -> dict:
    """{id: nombre} de los métodos de pago indicados; falla si alguno no
    existe o está desactivado (él o su caja)."""
    filas = {m["id"]: m["nombre"] for m in conn.execute(
        """SELECT m.id, m.nombre FROM metodos_pago m JOIN cajas c ON c.id = m.caja_id
            WHERE m.id = ANY(%s) AND m.activo AND c.activo""", (ids,))}
    if len(filas) != len(set(ids)):
        raise ErrorNegocio("Uno de los métodos de pago no existe o está desactivado.")
    return filas


def _exigir_cupo(conn, cliente_id, fiado: Decimal) -> dict:
    if cliente_id is None:
        raise ErrorNegocio("Para fiar elige el cliente.")
    cupo = cupo_cliente(conn, cliente_id, bloquear=True)
    if not cupo["activo"]:
        raise ErrorNegocio(f"{cupo['nombre']} está desactivado como cliente: no se le fía.")
    if cupo["limite_credito"] == 0:
        raise ErrorNegocio(f"{cupo['nombre']} no tiene cupo de fiado: asígnaselo en Clientes.")
    if fiado > cupo["disponible"]:
        raise ErrorNegocio(f"{cupo['nombre']} tiene disponible {pesos(cupo['disponible'])} de fiado "
                           f"(cupo {pesos(cupo['limite_credito'])}, debe {pesos(cupo['saldo'])}).")
    return cupo


def registrar_venta(conn, actor: Usuario, sesion_id, lineas: list[dict], *, descuento: Decimal = Decimal(0),
                    pagos: list[dict] = (), fiado: Decimal = Decimal(0), cliente_id=None, notas: str | None = None,
                    origen: str | None = None, exigir_activos: bool = True) -> dict:
    """lineas = [{articulo_id, cantidad, precio_unit?}]: sin precio_unit se usa
    el precio actual (venta directa); una cuenta manda el que fotografió al
    agregar cada ítem y no exige que el artículo siga activo (ya se consumió).
    pagos = [{metodo_pago_id, monto}]. origen describe de dónde viene (ej. "la
    cuenta #4") para la auditoría. Retorna el detalle."""
    numero_turno = exigir_turno_abierto(conn, sesion_id)
    if not lineas:
        raise ErrorNegocio("La venta no tiene productos.")
    articulos = _articulos(conn, [l["articulo_id"] for l in lineas], exigir_activos)
    precios = [l.get("precio_unit") if l.get("precio_unit") is not None
               else articulos[l["articulo_id"]]["precio_venta"] for l in lineas]
    subtotal = _redondear(sum((Decimal(l["cantidad"]) * p for l, p in zip(lineas, precios)), Decimal(0)))
    if descuento > subtotal:
        raise ErrorNegocio(f"El descuento ({pesos(descuento)}) supera el subtotal ({pesos(subtotal)}).")
    total = subtotal - descuento

    pagos = list(pagos)
    metodos = nombres_metodos(conn, [p["metodo_pago_id"] for p in pagos]) if pagos else {}
    cobrado = sum((p["monto"] for p in pagos), Decimal(0)) + fiado
    if cobrado < total:
        raise ErrorNegocio(f"Falta cobrar {pesos(total - cobrado)}: el total es {pesos(total)}.")
    if cobrado > total:
        raise ErrorNegocio(f"Se está cobrando {pesos(cobrado - total)} de más: el total es {pesos(total)} "
                           "(el cambio no se registra como pago).")
    cupo = _exigir_cupo(conn, cliente_id, fiado) if fiado > 0 else None
    if cliente_id is not None and cupo is None:
        exigir_cliente(conn, cliente_id)

    venta = conn.execute(
        """INSERT INTO ventas (sesion_id, usuario_id, cliente_id, descuento, notas)
           VALUES (%s, %s, %s, %s, %s) RETURNING id, numero""",
        (sesion_id, actor.id, cliente_id, descuento, notas),
    ).fetchone()
    # Todas las líneas en UN solo INSERT: el trigger de stock es por sentencia
    # y bloquea los productos en orden (ver 0015).
    conn.execute(
        """INSERT INTO detalle_venta (venta_id, articulo_id, cantidad, precio_unit, costo_unit, impuesto_id)
           SELECT %s, a.id, x.cantidad, x.precio, COALESCE(costo_articulo(a.id), 0), a.impuesto_id
             FROM unnest(%s::uuid[], %s::numeric[], %s::numeric[]) WITH ORDINALITY AS x(articulo, cantidad, precio, n)
             JOIN articulos a ON a.id = x.articulo
            ORDER BY x.n""",
        (venta["id"], [l["articulo_id"] for l in lineas], [l["cantidad"] for l in lineas], precios),
    )
    if pagos:
        conn.cursor().executemany(
            "INSERT INTO pagos_venta (venta_id, metodo_pago_id, monto) VALUES (%s, %s, %s)",
            [(venta["id"], p["metodo_pago_id"], p["monto"]) for p in pagos],
        )
    if cupo is not None:
        conn.execute(
            """INSERT INTO cargos_credito (cliente_id, venta_id, monto, vence_en)
               VALUES (%s, %s, %s, current_date + %s)""",
            (cliente_id, venta["id"], fiado, cupo["dias_credito"]),
        )

    partes = [f"{metodos[p['metodo_pago_id']]} {pesos(p['monto'])}" for p in pagos]
    if cupo is not None:
        partes.append(f"fiado {pesos(fiado)} a {cupo['nombre']}")
    detalle = f"Venta #{venta['numero']} por {pesos(total)} en el turno #{numero_turno}"
    if origen:
        detalle += f", de {origen}"
    detalle += ": " + ", ".join(partes)
    if descuento:
        detalle += f" (descuento {pesos(descuento)})"
    auditar(conn, actor.id, "venta", detalle, "ventas", venta["id"])
    return detalle_venta(conn, venta["id"])
