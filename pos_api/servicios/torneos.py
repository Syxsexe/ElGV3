"""
pos_api/servicios/torneos.py — Torneos de TCG: jugadores, inscripciones y premios.

Un torneo se registra completo en una transacción. Las inscripciones pagadas
son UNA venta del servicio de inscripción (cantidad = jugadores que pagan):
cada jugador apunta a su pago (pagos_venta) o a su cargo fiado
(cargos_credito, uno por jugador, dentro del cupo de cada cliente); los que
entran gratis no apuntan a nada. Los premios guardan el costo del producto y
descuentan stock por trigger. Recaudado, costo de premios, ganancia y
jugadores salen de v_torneos.

No se edita ni se anula (su venta tampoco). Lo registra cualquier usuario
con sesión.
"""
import uuid
from decimal import Decimal

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado
from pos_api.seguridad import Usuario
from pos_api.servicios.caja import exigir_turno_abierto
from pos_api.servicios.comun import condicion_busqueda, literal_like, pesos
from pos_api.servicios.ventas import exigir_cupo, nombres_metodos

# El servicio sembrado en 0013. Se busca por nombre si no se indica otro.
INSCRIPCION = "Inscripción a torneo"


def premios_disponibles(conn, texto: str) -> list[dict]:
    """Productos de tienda activos que sirven de premio, con su costo y precio
    de venta (el formulario suma lo que vale la premiación)."""
    return conn.execute(
        """SELECT id, nombre, stock, precio_venta, precio_costo AS costo
             FROM v_articulos
            WHERE activo AND tipo = 'producto' AND categoria_tipo = 'tienda'
              AND (""" + condicion_busqueda("nombre") + """ OR codigo = %(texto)s)
            ORDER BY nombre
            LIMIT 30""",
        {"patron": literal_like(texto), "texto": texto.strip()},
    ).fetchall()


def inscripcion(conn, articulo_id=None) -> dict:
    """El servicio con que se cobran las inscripciones (y su precio actual)."""
    fila = conn.execute(
        """SELECT id, nombre, precio_venta AS precio FROM articulos
            WHERE tipo = 'servicio' AND activo AND (id = %s OR (%s::uuid IS NULL AND nombre = %s))""",
        (articulo_id, articulo_id, INSCRIPCION),
    ).fetchone()
    if fila is None:
        if articulo_id is not None:
            raise NoEncontrado("El servicio de inscripción no existe o está desactivado.")
        raise ErrorNegocio(f"No existe el servicio «{INSCRIPCION}» activo: créalo en Inventario (Servicios).")
    return fila


# ── Consultas ───────────────────────────────────────────────────────────────

_TORNEO = """
    SELECT t.id, t.nombre, t.juego_id, t.juego, t.realizado_en, t.notas, t.recaudado, t.costo_premios, t.ganancia,
           t.jugadores, t.jugadores_gratis, t.venta_id, v.numero AS venta_numero, u.usuario
      FROM v_torneos t
      JOIN usuarios u ON u.id = t.usuario_id
      LEFT JOIN ventas v ON v.id = t.venta_id
"""


def listar_torneos(conn, *, desde=None, hasta=None, juego_id=None, limite: int = 200) -> list[dict]:
    return conn.execute(
        _TORNEO + """
         WHERE (%(desde)s::date IS NULL OR t.realizado_en >= %(desde)s::date)
           AND (%(hasta)s::date IS NULL OR t.realizado_en < %(hasta)s::date + 1)
           AND (%(juego)s::uuid IS NULL OR t.juego_id = %(juego)s)
         ORDER BY t.realizado_en DESC, t.id DESC
         LIMIT %(limite)s""",
        {"desde": desde, "hasta": hasta, "juego": juego_id, "limite": limite},
    ).fetchall()


def detalle_torneo(conn, torneo_id) -> dict:
    torneo = conn.execute(_TORNEO + " WHERE t.id = %s", (torneo_id,)).fetchone()
    if torneo is None:
        raise NoEncontrado("El torneo no existe.")
    torneo["participantes"] = conn.execute(
        """SELECT tp.id, tp.cliente_id, COALESCE(t.nombre, tp.alias) AS nombre,
                  CASE WHEN tp.pago_venta_id IS NOT NULL THEN mp.nombre
                       WHEN tp.cargo_id IS NOT NULL THEN 'Crédito' ELSE 'Gratis' END AS forma,
                  COALESCE(pv.monto, c.monto, 0) AS monto
             FROM torneo_participantes tp
             LEFT JOIN terceros t ON t.id = tp.cliente_id
             LEFT JOIN pagos_venta pv ON pv.id = tp.pago_venta_id
             LEFT JOIN metodos_pago mp ON mp.id = pv.metodo_pago_id
             LEFT JOIN cargos_credito c ON c.id = tp.cargo_id
            WHERE tp.torneo_id = %s ORDER BY tp.id""",
        (torneo_id,),
    ).fetchall()
    torneo["premios"] = conn.execute(
        """SELECT tp.producto_id, a.nombre, tp.cantidad, tp.costo_unit, round(tp.cantidad * tp.costo_unit, 2) AS costo
             FROM torneo_premios tp JOIN articulos a ON a.id = tp.producto_id
            WHERE tp.torneo_id = %s ORDER BY a.nombre""",
        (torneo_id,),
    ).fetchall()
    return torneo


# ── Registro ────────────────────────────────────────────────────────────────

def registrar_torneo(conn, actor: Usuario, *, nombre: str, juego_id, participantes: list[dict],
                     premios: list[dict] = (), precio: Decimal | None = None, sesion_id=None,
                     inscripcion_id=None, notas: str | None = None) -> dict:
    """participantes = [{cliente_id | alias, forma: "pago" | "fiado" | "gratis",
    metodo_pago_id (si forma = pago)}]. precio: el de cada inscripción (por
    defecto el del servicio). sesion_id: el turno en pantalla, obligatorio si
    alguien paga o fía. premios = [{producto_id, cantidad}]: productos de
    tienda activos (salen del inventario). La fecha es la del registro: la
    plata entra al turno abierto."""
    # ── Validar todo antes de escribir ──
    juego = conn.execute("SELECT nombre, activo FROM juegos WHERE id = %s", (juego_id,)).fetchone()
    if juego is None:
        raise NoEncontrado("El juego no existe.")
    if not juego["activo"]:
        raise ErrorNegocio(f"El juego {juego['nombre']} está desactivado.")
    if not participantes:
        raise ErrorNegocio("El torneo no tiene jugadores.")
    for p in participantes:
        if bool(p.get("cliente_id")) == bool(p.get("alias")):
            raise ErrorNegocio("Cada jugador es un cliente registrado o un nombre (uno de los dos).")
        if p["forma"] == "fiado" and not p.get("cliente_id"):
            raise ErrorNegocio(f"{p['alias']} no es cliente registrado: no se le puede dar crédito.")
        if p["forma"] == "pago" and not p.get("metodo_pago_id"):
            raise ErrorNegocio("A cada jugador que paga indícale el método.")
    clientes = [p["cliente_id"] for p in participantes if p.get("cliente_id")]
    if len(clientes) != len(set(clientes)):
        raise ErrorNegocio("Un cliente está inscrito dos veces.")
    registrados = conn.execute(
        """SELECT t.nombre, cl.activo FROM clientes cl JOIN terceros t ON t.id = cl.tercero_id
            WHERE cl.tercero_id = ANY(%s)""", (clientes,)).fetchall()
    if len(registrados) != len(clientes):
        raise NoEncontrado("Uno de los clientes no existe.")
    inactivos = sorted(c["nombre"] for c in registrados if not c["activo"])
    if inactivos:
        raise ErrorNegocio(f"Están desactivados como clientes: {', '.join(inactivos)}.")

    premios = list(premios)
    ids_premios = [p["producto_id"] for p in premios]
    if len(ids_premios) != len(set(ids_premios)):
        raise ErrorNegocio("Un premio aparece dos veces: junta las cantidades.")
    if premios:
        validos = conn.execute(
            """SELECT count(*) AS n FROM articulos a JOIN productos p ON p.articulo_id = a.id
                 JOIN categorias c ON c.id = a.categoria_id
                WHERE a.id = ANY(%s) AND a.activo AND c.tipo = 'tienda'""", (ids_premios,)).fetchone()["n"]
        if validos != len(ids_premios):
            raise ErrorNegocio("Los premios son productos de tienda activos (los que tienen stock).")

    pagan = [p for p in participantes if p["forma"] != "gratis"]
    venta = None
    if pagan:
        if sesion_id is None:
            raise ErrorNegocio("Para cobrar inscripciones indica el turno de caja.")
        numero_turno = exigir_turno_abierto(conn, sesion_id)
        servicio = inscripcion(conn, inscripcion_id)
        precio = servicio["precio"] if precio is None else precio
        if precio <= 0:
            raise ErrorNegocio("Con inscripción en $0 los jugadores entran gratis: márcalos así.")
        metodos = nombres_metodos(conn, list({p["metodo_pago_id"] for p in pagan if p["forma"] == "pago"}))
        # El cupo bloquea la fila de cada cliente: en orden de id, para que dos
        # torneos con los mismos clientes fiados se esperen en vez de trabarse.
        fiados = sorted((p for p in pagan if p["forma"] == "fiado"), key=lambda p: str(p["cliente_id"]))
        dias = {p["cliente_id"]: exigir_cupo(conn, p["cliente_id"], precio)["dias_credito"] for p in fiados}

    # ── Escribir ──
    if pagan:
        venta = conn.execute(
            "INSERT INTO ventas (sesion_id, usuario_id) VALUES (%s, %s) RETURNING id, numero", (sesion_id, actor.id),
        ).fetchone()
        conn.execute(
            """INSERT INTO detalle_venta (venta_id, articulo_id, cantidad, precio_unit, costo_unit, impuesto_id)
               SELECT %s, id, %s, %s, 0, impuesto_id FROM articulos WHERE id = %s""",
            (venta["id"], len(pagan), precio, servicio["id"]),
        )
        # Cada jugador con su propio pago o cargo. Los ids se generan aquí
        # (UUIDv7, como los de la base) para insertar en lote y saber cuál es
        # de quién.
        for p in pagan:
            p["pago_venta_id" if p["forma"] == "pago" else "cargo_id"] = uuid.uuid7()
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT INTO pagos_venta (id, venta_id, metodo_pago_id, monto) VALUES (%s, %s, %s, %s)",
            [(p["pago_venta_id"], venta["id"], p["metodo_pago_id"], precio) for p in pagan if p["forma"] == "pago"],
        )
        cursor.executemany(
            """INSERT INTO cargos_credito (id, cliente_id, venta_id, monto, vence_en)
               VALUES (%s, %s, %s, %s, current_date + %s)""",
            [(p["cargo_id"], p["cliente_id"], venta["id"], precio, dias[p["cliente_id"]]) for p in fiados],
        )

    torneo = conn.execute(
        "INSERT INTO torneos (nombre, juego_id, usuario_id, venta_id, notas) VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (nombre, juego_id, actor.id, venta["id"] if venta else None, notas),
    ).fetchone()
    conn.cursor().executemany(
        """INSERT INTO torneo_participantes (torneo_id, cliente_id, alias, pago_venta_id, cargo_id)
           VALUES (%s, %s, %s, %s, %s)""",
        [(torneo["id"], p.get("cliente_id"), p.get("alias"), p.get("pago_venta_id"), p.get("cargo_id"))
         for p in participantes],
    )
    if premios:
        # En UN solo INSERT: el trigger de stock es por sentencia. El costo es
        # la foto del costo actual del producto.
        conn.execute(
            """INSERT INTO torneo_premios (torneo_id, producto_id, cantidad, costo_unit)
               SELECT %s, p.articulo_id, x.cantidad, p.precio_costo
                 FROM unnest(%s::uuid[], %s::numeric[]) AS x(producto, cantidad)
                 JOIN productos p ON p.articulo_id = x.producto""",
            (torneo["id"], ids_premios, [p["cantidad"] for p in premios]),
        )

    detalle = detalle_torneo(conn, torneo["id"])
    gratis = len(participantes) - len(pagan)
    texto = (f"Registró el torneo «{nombre}» ({juego['nombre']}): {len(participantes)} jugador(es)"
             + (f", {gratis} gratis" if gratis else ""))
    if venta:
        formas = {}
        for p in pagan:
            clave = metodos[p["metodo_pago_id"]] if p["forma"] == "pago" else "crédito"
            formas[clave] = formas.get(clave, 0) + precio
        texto += (f"; recaudó {pesos(detalle['recaudado'])} en la venta #{venta['numero']} del turno #{numero_turno} ("
                  + ", ".join(f"{k} {pesos(v)}" for k, v in formas.items()) + ")")
    if premios:
        texto += f"; premios por {pesos(detalle['costo_premios'])}"
    auditar(conn, actor.id, "torneo", texto, "torneos", torneo["id"])
    return detalle
