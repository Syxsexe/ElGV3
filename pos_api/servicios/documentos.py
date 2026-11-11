"""
pos_api/servicios/documentos.py — Documentos comerciales: cotización → orden
de pedido → remisión → venta.

Cada documento lleva líneas del catálogo (con el precio acordado, que puede
no ser el de lista) o de texto libre. El estado sale de
v_documentos_comerciales: vigente o vencida (abierto), aceptada / entregada
(ya se convirtió en el siguiente de la cadena), facturada (ya es una venta),
rechazada o anulada (descartado).

Reglas de la API (la base solo cuida la cadena de tipos y los consecutivos):
- Un documento abierto se edita y se descarta; uno cerrado ya no cambia.
- Convertir y vender exigen que esté vigente (una cotización vencida se
  renueva editando su vigencia).
- Vender exige que todas las líneas sean del catálogo: una línea de venta
  siempre apunta a un artículo. Los artículos desactivados no entran en
  documentos nuevos o editados.
- Descartar un documento reabre el de origen.

Lo hace cualquier usuario con sesión.
"""
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado
from pos_api.seguridad import Usuario
from pos_api.servicios.comun import condicion_busqueda, literal_like, pesos
from pos_api.servicios.ventas import exigir_cliente, registrar_venta

NOMBRE = {"cotizacion": "cotización", "orden_pedido": "orden de pedido", "remision": "remisión"}
SIGUIENTE = {"cotizacion": "orden_pedido", "orden_pedido": "remision"}
ABIERTOS = ("vigente", "vencida")

_DOCUMENTO = """
    SELECT d.id, d.tipo, d.numero, d.cliente_id, t.nombre AS cliente, d.creado_en, d.descuento, d.vigente_hasta,
           d.doc_origen_id, o.tipo AS origen_tipo, o.numero AS origen_numero, d.venta_id, v.numero AS venta_numero,
           d.descartado_en, d.motivo_descarte, d.notas, d.subtotal, d.total, d.estado, u.usuario,
           h.id AS hijo_id, h.tipo AS hijo_tipo, h.numero AS hijo_numero,
           (SELECT count(*) FROM documento_items di WHERE di.documento_id = d.id) AS lineas
      FROM v_documentos_comerciales d
      JOIN usuarios u ON u.id = d.usuario_id
      LEFT JOIN terceros t ON t.id = d.cliente_id
      LEFT JOIN documentos_comerciales o ON o.id = d.doc_origen_id
      LEFT JOIN ventas v ON v.id = d.venta_id
      LEFT JOIN LATERAL (SELECT id, tipo, numero FROM documentos_comerciales
                          WHERE doc_origen_id = d.id
                          ORDER BY descartado_en IS NOT NULL, creado_en DESC LIMIT 1) h ON true
"""


def _titulo(doc: dict) -> str:
    return f"la {NOMBRE[doc['tipo']]} #{doc['numero']}"


# ── Consultas ───────────────────────────────────────────────────────────────

def listar_documentos(conn, *, tipo: str | None = None, estado: str | None = None, texto: str | None = None,
                      limite: int = 200) -> list[dict]:
    """texto busca por nombre del cliente o por número."""
    numero = (texto or "").strip().lstrip("#")
    return conn.execute(
        _DOCUMENTO + f"""
         WHERE (%(tipo)s::text IS NULL OR d.tipo = %(tipo)s)
           AND (%(estado)s::text IS NULL OR d.estado = %(estado)s
                OR (%(estado)s = 'abierto' AND d.estado IN ('vigente', 'vencida')))
           AND (%(patron)s::text IS NULL OR {condicion_busqueda("t.nombre")}
                OR (%(numero)s ~ '^[0-9]{{1,18}}$' AND d.numero = %(numero)s::bigint))
         ORDER BY d.creado_en DESC, d.id DESC
         LIMIT %(limite)s""",
        {"tipo": tipo, "estado": estado, "patron": literal_like(texto), "numero": numero, "limite": limite},
    ).fetchall()


def detalle_documento(conn, documento_id) -> dict:
    doc = conn.execute(_DOCUMENTO + " WHERE d.id = %s", (documento_id,)).fetchone()
    if doc is None:
        raise NoEncontrado("El documento no existe.")
    doc["items"] = conn.execute(
        """SELECT di.id, di.articulo_id, a.nombre AS articulo, a.activo AS articulo_activo, di.descripcion,
                  di.cantidad, di.precio_unit, di.impuesto_id, im.codigo AS impuesto,
                  round(di.cantidad * di.precio_unit, 2) AS subtotal
             FROM documento_items di
             LEFT JOIN articulos a ON a.id = di.articulo_id
             LEFT JOIN impuestos im ON im.id = di.impuesto_id
            WHERE di.documento_id = %s ORDER BY di.id""",
        (documento_id,),
    ).fetchall()
    return doc


# ── Escritura ───────────────────────────────────────────────────────────────

def _tomar(conn, documento_id, con_items: bool = True) -> dict:
    """Bloquea el documento (dos pantallas no lo convierten o venden a la vez)
    y lo lee, con sus líneas si hacen falta."""
    if conn.execute("SELECT 1 FROM documentos_comerciales WHERE id = %s FOR UPDATE", (documento_id,)).fetchone() is None:
        raise NoEncontrado("El documento no existe.")
    if con_items:
        return detalle_documento(conn, documento_id)
    return conn.execute(_DOCUMENTO + " WHERE d.id = %s", (documento_id,)).fetchone()


def _exigir_abierto(doc: dict, para: str) -> None:
    if doc["estado"] in ABIERTOS:
        return
    detalle = {
        "aceptada": f"ya se convirtió en la {NOMBRE.get(doc['hijo_tipo'], '')} #{doc['hijo_numero']}",
        "entregada": f"ya se convirtió en la {NOMBRE.get(doc['hijo_tipo'], '')} #{doc['hijo_numero']}",
        "facturada": f"ya se vendió (venta #{doc['venta_numero']})",
        "rechazada": "fue rechazada", "anulada": "fue anulada",
    }[doc["estado"]]
    raise ErrorNegocio(f"No se puede {para} {_titulo(doc)}: {detalle}.")


def _exigir_vigente(doc: dict, para: str) -> None:
    _exigir_abierto(doc, para)
    if doc["estado"] == "vencida":
        raise ErrorNegocio(f"{_titulo(doc).capitalize()} venció el {doc['vigente_hasta']}: "
                           "actualiza su vigencia antes de seguir.")


def _preparar_items(conn, items: list[dict]) -> tuple[list[tuple], Decimal]:
    """Valida las líneas y las completa con el artículo (descripción = nombre,
    precio = precio de lista, impuesto) en lo que no se indique. Retorna las
    filas (articulo_id, descripcion, cantidad, precio, impuesto) y el subtotal."""
    if not items:
        raise ErrorNegocio("El documento no tiene líneas.")
    ids = [i["articulo_id"] for i in items if i.get("articulo_id")]
    articulos = {a["id"]: a for a in conn.execute(
        "SELECT id, nombre, activo, precio_venta, impuesto_id FROM articulos WHERE id = ANY(%s)", (ids,))}
    if len(articulos) != len(set(ids)):
        raise NoEncontrado("Uno de los artículos no existe.")
    inactivos = sorted(a["nombre"] for a in articulos.values() if not a["activo"])
    if inactivos:
        raise ErrorNegocio(f"Ya no se vende: {', '.join(inactivos)}. Quítalo del documento o usa otro artículo.")
    filas, subtotal = [], Decimal(0)
    for i in items:
        a = articulos.get(i.get("articulo_id"))
        descripcion = i.get("descripcion") or (a["nombre"] if a else None)
        if not descripcion:
            raise ErrorNegocio("Una línea de texto libre necesita su descripción.")
        precio = i.get("precio_unit") if i.get("precio_unit") is not None else (a["precio_venta"] if a else None)
        if precio is None:
            raise ErrorNegocio(f"La línea «{descripcion}» necesita su precio.")
        filas.append((i.get("articulo_id"), descripcion, i["cantidad"], precio,
                      i.get("impuesto_id") or (a["impuesto_id"] if a else None)))
        subtotal += Decimal(i["cantidad"]) * Decimal(precio)
    return filas, subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _exigir_descuento(descuento: Decimal, subtotal: Decimal) -> None:
    if descuento > subtotal:
        raise ErrorNegocio(f"El descuento ({pesos(descuento)}) supera el subtotal ({pesos(subtotal)}).")


def _insertar_items(conn, documento_id, filas: list[tuple]) -> None:
    conn.cursor().executemany(
        """INSERT INTO documento_items (documento_id, articulo_id, descripcion, cantidad, precio_unit, impuesto_id)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        [(documento_id, *f) for f in filas],
    )


def crear_documento(conn, actor: Usuario, tipo: str, items: list[dict], *, cliente_id=None,
                    descuento: Decimal = Decimal(0), vigente_hasta: date | None = None,
                    notas: str | None = None) -> dict:
    if vigente_hasta is not None and tipo != "cotizacion":
        raise ErrorNegocio("Solo una cotización lleva fecha de vigencia.")
    if cliente_id is not None:
        exigir_cliente(conn, cliente_id)
    filas, subtotal = _preparar_items(conn, items)
    _exigir_descuento(descuento, subtotal)
    # El INSERT toma el consecutivo: va después de validar, para no gastar números.
    fila = conn.execute(
        """INSERT INTO documentos_comerciales (tipo, cliente_id, usuario_id, descuento, vigente_hasta, notas)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (tipo, cliente_id, actor.id, descuento, vigente_hasta, notas),
    ).fetchone()
    _insertar_items(conn, fila["id"], filas)
    doc = detalle_documento(conn, fila["id"])
    auditar(conn, actor.id, "documento", f"Creó {_titulo(doc)} por {pesos(doc['total'])}"
            + (f" para {doc['cliente']}" if doc["cliente"] else ""), "documentos_comerciales", doc["id"])
    return doc


def editar_documento(conn, actor: Usuario, documento_id, items: list[dict], *, cliente_id=None,
                     descuento: Decimal = Decimal(0), vigente_hasta: date | None = None,
                     notas: str | None = None) -> dict:
    """Reemplaza el documento completo (encabezado y líneas) mientras esté abierto."""
    doc = _tomar(conn, documento_id, con_items=False)
    _exigir_abierto(doc, "editar")
    if vigente_hasta is not None and doc["tipo"] != "cotizacion":
        raise ErrorNegocio("Solo una cotización lleva fecha de vigencia.")
    if cliente_id is not None:
        exigir_cliente(conn, cliente_id)
    filas, subtotal = _preparar_items(conn, items)
    _exigir_descuento(descuento, subtotal)
    conn.execute(
        """UPDATE documentos_comerciales SET cliente_id = %s, descuento = %s, vigente_hasta = %s, notas = %s
            WHERE id = %s""",
        (cliente_id, descuento, vigente_hasta, notas, documento_id),
    )
    conn.execute("DELETE FROM documento_items WHERE documento_id = %s", (documento_id,))
    _insertar_items(conn, documento_id, filas)
    nuevo = detalle_documento(conn, documento_id)
    auditar(conn, actor.id, "documento", f"Editó {_titulo(nuevo)}: total {pesos(doc['total'])} → {pesos(nuevo['total'])}",
            "documentos_comerciales", documento_id)
    return nuevo


def convertir(conn, actor: Usuario, documento_id) -> dict:
    """Crea el siguiente documento de la cadena con las mismas líneas, cliente
    y descuento. El origen queda aceptado (cotización) o entregado (orden)."""
    doc = _tomar(conn, documento_id, con_items=False)
    if doc["tipo"] not in SIGUIENTE:
        raise ErrorNegocio("Una remisión no se convierte en otro documento: se vende.")
    _exigir_vigente(doc, "convertir")
    tipo = SIGUIENTE[doc["tipo"]]
    fila = conn.execute(
        """INSERT INTO documentos_comerciales (tipo, cliente_id, usuario_id, descuento, doc_origen_id, notas)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (tipo, doc["cliente_id"], actor.id, doc["descuento"], documento_id, doc["notas"]),
    ).fetchone()
    conn.execute(
        """INSERT INTO documento_items (documento_id, articulo_id, descripcion, cantidad, precio_unit, impuesto_id)
           SELECT %s, articulo_id, descripcion, cantidad, precio_unit, impuesto_id
             FROM documento_items WHERE documento_id = %s ORDER BY id""",
        (fila["id"], documento_id),
    )
    nuevo = detalle_documento(conn, fila["id"])
    auditar(conn, actor.id, "documento", f"Convirtió {_titulo(doc)} en {_titulo(nuevo)}",
            "documentos_comerciales", nuevo["id"])
    return nuevo


def vender(conn, actor: Usuario, documento_id, sesion_id, *, pagos: list[dict], fiado: Decimal,
           cliente_id=None, notas: str | None = None) -> dict:
    """Pasa las líneas a una venta en el turno indicado, con los precios y el
    descuento del documento. El cliente de la venta es el indicado o, si no,
    el del documento. Retorna la venta (con el documento en `documento`)."""
    doc = _tomar(conn, documento_id)
    _exigir_vigente(doc, "vender")
    libres = [i["descripcion"] for i in doc["items"] if i["articulo_id"] is None]
    if libres:
        raise ErrorNegocio(f"Para vender, cada línea debe ser un artículo del catálogo. Edita {_titulo(doc)} y "
                           f"cambia las de texto libre: {', '.join(libres)}.")
    lineas = [{"articulo_id": i["articulo_id"], "cantidad": i["cantidad"], "precio_unit": i["precio_unit"],
               "impuesto_id": i["impuesto_id"]} for i in doc["items"]]
    venta = registrar_venta(conn, actor, sesion_id, lineas, descuento=doc["descuento"], pagos=pagos, fiado=fiado,
                            cliente_id=cliente_id or doc["cliente_id"], notas=notas, origen=_titulo(doc),
                            exigir_activos=False)
    conn.execute("UPDATE documentos_comerciales SET venta_id = %s WHERE id = %s", (venta["id"], documento_id))
    venta["documento"] = detalle_documento(conn, documento_id)
    return venta


def descartar(conn, actor: Usuario, documento_id, motivo: str, explicacion: str | None = None) -> dict:
    """motivo: "rechazado" (el cliente no lo aceptó) o "anulado" (error). La
    explicación queda en las notas y en la auditoría. Si venía de otro
    documento, ese vuelve a quedar abierto (v_documentos_comerciales, 0020)."""
    doc = _tomar(conn, documento_id, con_items=False)
    _exigir_abierto(doc, "descartar")
    conn.execute(
        """UPDATE documentos_comerciales
              SET descartado_en = now(), motivo_descarte = %(motivo)s,
                  notas = CASE WHEN %(explicacion)s::text IS NULL THEN notas
                               ELSE concat_ws(E'\\n', notas, 'Descartado: ' || %(explicacion)s) END
            WHERE id = %(id)s""",
        {"motivo": motivo, "explicacion": explicacion, "id": documento_id},
    )
    auditar(conn, actor.id, "documento",
            f"Marcó {_titulo(doc)} como {motivo}" + (f": {explicacion}" if explicacion else ""),
            "documentos_comerciales", documento_id)
    return detalle_documento(conn, documento_id)
