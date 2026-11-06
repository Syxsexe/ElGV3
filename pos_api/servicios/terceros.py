"""
pos_api/servicios/terceros.py — Clientes y proveedores.

Toda persona o empresa es un tercero; cliente y proveedor son roles que se le
agregan (un tercero puede tener ambos). Dos terceros no se editan desde aquí:
CONSUMIDOR FINAL (el adquiriente genérico de la DIAN) y el propio negocio
(se edita en Configuración).

Permisos: cualquier usuario crea y edita los datos de un tercero y le da el
rol de cliente sin cupo (el cajero registra clientes al vender). Cambiar el
cupo, los días de crédito o desactivar un cliente exige clientes.editar; el
rol de proveedor exige compras.registrar.
"""
from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado, SinPermiso
from pos_api.seguridad import Usuario
from pos_api.servicios.comun import (actualizar, condicion_busqueda, digito_verificacion, limpiar_numero,
                                     literal_like, normalizar_documento, tipo_identificacion_id)

PERMISO_CLIENTES = "clientes.editar"
PERMISO_PROVEEDORES = "compras.registrar"
DIAS_CREDITO_POR_DEFECTO = 30

CAMPOS_TERCERO = {"tipo_persona", "nombre", "direccion", "municipio_id", "telefono", "email", "responsable_iva"}

_SELECT = """
    SELECT t.id, t.nombre, t.tipo_persona, ti.codigo AS tipo_identificacion,
           ti.nombre AS tipo_identificacion_nombre, t.numero_identificacion,
           t.direccion, t.municipio_id, m.nombre AS municipio, d.nombre AS departamento,
           t.telefono, t.email, t.responsable_iva, t.creado_en,
           (cl.tercero_id IS NOT NULL) AS es_cliente, cl.limite_credito, cl.dias_credito,
           cl.activo AS cliente_activo,
           (pr.tercero_id IS NOT NULL) AS es_proveedor, pr.contacto, pr.activo AS proveedor_activo,
           u.id AS usuario_id, u.usuario
      FROM terceros t
      LEFT JOIN tipos_identificacion ti ON ti.id = t.tipo_identificacion_id
      LEFT JOIN municipios m ON m.id = t.municipio_id
      LEFT JOIN departamentos d ON d.id = m.departamento_id
      LEFT JOIN clientes cl ON cl.tercero_id = t.id
      LEFT JOIN proveedores pr ON pr.tercero_id = t.id
      LEFT JOIN usuarios u ON u.tercero_id = t.id
"""

# Terceros que no son "de nadie": el adquiriente genérico (marcado en 0018) y
# el propio negocio.
_PROTEGIDOS = "(NOT t.es_consumidor_final AND t.id NOT IN (SELECT tercero_id FROM empresa))"


def _con_dv(fila: dict) -> dict:
    nit = fila["tipo_identificacion"] == "31" and fila["numero_identificacion"]
    fila["dv"] = digito_verificacion(fila["numero_identificacion"]) if nit else None
    return fila


def _guardar_responsabilidades(conn, tercero_id, codigos: list[str]) -> None:
    validos = {r["codigo"] for r in conn.execute(
        "SELECT codigo FROM responsabilidades_fiscales WHERE codigo = ANY (%s)", (codigos,))}
    desconocidas = sorted(set(codigos) - validos)
    if desconocidas:
        raise ErrorNegocio(f"Responsabilidades fiscales desconocidas: {', '.join(desconocidas)}.")
    conn.execute("DELETE FROM tercero_responsabilidades WHERE tercero_id = %s", (tercero_id,))
    conn.execute(
        """INSERT INTO tercero_responsabilidades (tercero_id, responsabilidad_id)
           SELECT %s, id FROM responsabilidades_fiscales WHERE codigo = ANY (%s)""",
        (tercero_id, codigos),
    )


def exigir_no_protegido(conn, tercero_id, bloquear: bool = False) -> str:
    """Falla si el tercero no existe o es CONSUMIDOR FINAL / el negocio; si
    no, retorna su nombre (y con bloquear=True deja la fila tomada)."""
    fila = conn.execute(
        f"SELECT t.nombre, {_PROTEGIDOS} AS editable FROM terceros t WHERE t.id = %s"
        + (" FOR UPDATE" if bloquear else ""), (tercero_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("El tercero no existe.")
    if not fila["editable"]:
        raise ErrorNegocio("Este tercero no se usa aquí (CONSUMIDOR FINAL o el propio negocio, que va en Configuración).")
    return fila["nombre"]


# ── Consultas ───────────────────────────────────────────────────────────────

def listar_terceros(conn, *, rol: str | None = None, texto: str | None = None,
                    solo_activos: bool = False, limite: int = 200) -> list[dict]:
    """rol: "cliente" o "proveedor" (None = todos). Busca por nombre (sin
    tildes) o por el comienzo del número de documento."""
    filas = conn.execute(
        _SELECT + f"""
         WHERE {_PROTEGIDOS}
           AND (%(rol)s::text IS NULL
                OR (%(rol)s = 'cliente' AND cl.tercero_id IS NOT NULL AND (NOT %(activos)s OR cl.activo))
                OR (%(rol)s = 'proveedor' AND pr.tercero_id IS NOT NULL AND (NOT %(activos)s OR pr.activo)))
           AND (%(patron)s::text IS NULL OR {condicion_busqueda("t.nombre")}
                OR (%(doc)s <> '' AND t.numero_identificacion LIKE %(doc)s || '%%'))
         ORDER BY t.nombre
         LIMIT %(limite)s""",
        {"rol": rol, "activos": solo_activos, "patron": literal_like(texto), "limite": limite,
         # El documento se busca como se guarda: sin puntos, espacios ni DV.
         "doc": literal_like(limpiar_numero(texto).split("-")[0]) or ""},
    ).fetchall()
    return [_con_dv(f) for f in filas]


def obtener_tercero(conn, tercero_id) -> dict:
    fila = conn.execute(_SELECT + " WHERE t.id = %s", (tercero_id,)).fetchone()
    if fila is None:
        raise NoEncontrado("El tercero no existe.")
    fila["responsabilidades"] = [r["codigo"] for r in conn.execute(
        """SELECT rf.codigo FROM tercero_responsabilidades tr
             JOIN responsabilidades_fiscales rf ON rf.id = tr.responsabilidad_id
            WHERE tr.tercero_id = %s ORDER BY rf.codigo""", (tercero_id,))]
    return _con_dv(fila)


def listar_responsabilidades(conn) -> list[dict]:
    return conn.execute("SELECT codigo, descripcion FROM responsabilidades_fiscales ORDER BY codigo").fetchall()


# ── Escritura ───────────────────────────────────────────────────────────────

def crear_tercero(conn, actor: Usuario, datos: dict, responsabilidades: list[str] | None = None,
                  cliente: dict | None = None, proveedor: dict | None = None) -> dict:
    """datos: campos del tercero + tipo_identificacion (código) y
    numero_identificacion. cliente/proveedor: si vienen, se le dan esos roles
    en la misma transacción (todo o nada)."""
    numero = normalizar_documento(datos.get("tipo_identificacion"), datos.get("numero_identificacion"))
    tercero_id = conn.execute(
        """INSERT INTO terceros (tipo_persona, nombre, tipo_identificacion_id, numero_identificacion,
                                 direccion, municipio_id, telefono, email, responsable_iva)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (datos.get("tipo_persona") or "natural", datos["nombre"], tipo_identificacion_id(conn, datos.get("tipo_identificacion")),
         numero, datos.get("direccion"), datos.get("municipio_id"), datos.get("telefono"),
         datos.get("email"), datos.get("responsable_iva")),
    ).fetchone()["id"]
    if responsabilidades:
        _guardar_responsabilidades(conn, tercero_id, responsabilidades)
    # Un proveedor nuevo queda en la auditoría de compras; lo demás, en la de clientes.
    accion = "compra" if proveedor is not None and cliente is None else "cliente"
    auditar(conn, actor.id, accion, f"Registró a {datos['nombre']}", "terceros", tercero_id)
    if cliente is not None:
        _rol_cliente(conn, actor, tercero_id, datos["nombre"], cliente)
    if proveedor is not None:
        _rol_proveedor(conn, actor, tercero_id, datos["nombre"], proveedor)
    return obtener_tercero(conn, tercero_id)


def editar_tercero(conn, actor: Usuario, tercero_id, cambios: dict, responsabilidades: list[str] | None = None,
                   cliente: dict | None = None, proveedor: dict | None = None) -> dict:
    """cambios: campos del tercero; tipo_identificacion y numero_identificacion
    se validan como par. responsabilidades None = no tocarlas. cliente /
    proveedor: datos del rol (lo da si no lo tenía). Todo en la misma
    transacción: si algo falla, no queda nada a medias."""
    exigir_no_protegido(conn, tercero_id, bloquear=True)
    antes = obtener_tercero(conn, tercero_id)
    columnas = {k: v for k, v in cambios.items() if k in CAMPOS_TERCERO and antes[k] != v}
    if "tipo_identificacion" in cambios or "numero_identificacion" in cambios:
        tipo = cambios.get("tipo_identificacion", antes["tipo_identificacion"])
        numero = normalizar_documento(tipo, cambios.get("numero_identificacion", antes["numero_identificacion"]))
        if (tipo, numero) != (antes["tipo_identificacion"], antes["numero_identificacion"]):
            columnas["tipo_identificacion_id"] = tipo_identificacion_id(conn, tipo)
            columnas["numero_identificacion"] = numero
    actualizar(conn, "terceros", tercero_id, columnas)
    detalle = [f"{k.removesuffix('_id')}: {antes.get(k)} → {v}" for k, v in columnas.items()
               if k != "tipo_identificacion_id"]
    if responsabilidades is not None and sorted(set(responsabilidades)) != antes["responsabilidades"]:
        _guardar_responsabilidades(conn, tercero_id, responsabilidades)
        detalle.append(f"responsabilidades: {', '.join(sorted(responsabilidades)) or 'ninguna'}")
    if detalle:
        auditar(conn, actor.id, "cliente", f"Editó a {antes['nombre']}: {'; '.join(detalle)}", "terceros", tercero_id)
    nombre = columnas.get("nombre", antes["nombre"])
    if cliente is not None:
        _rol_cliente(conn, actor, tercero_id, nombre, cliente)
    if proveedor is not None:
        _rol_proveedor(conn, actor, tercero_id, nombre, proveedor)
    return obtener_tercero(conn, tercero_id)


def guardar_cliente(conn, actor: Usuario, tercero_id, datos: dict) -> dict:
    """Da el rol de cliente o lo actualiza (limite_credito, dias_credito, activo)."""
    nombre = exigir_no_protegido(conn, tercero_id, bloquear=True)
    _rol_cliente(conn, actor, tercero_id, nombre, datos)
    return obtener_tercero(conn, tercero_id)


def guardar_proveedor(conn, actor: Usuario, tercero_id, datos: dict) -> dict:
    """Da el rol de proveedor o lo actualiza (contacto, activo)."""
    nombre = exigir_no_protegido(conn, tercero_id, bloquear=True)
    _rol_proveedor(conn, actor, tercero_id, nombre, datos)
    return obtener_tercero(conn, tercero_id)


def _rol_cliente(conn, actor: Usuario, tercero_id, nombre: str, datos: dict) -> None:
    """Lo que no venga en datos queda como está. Sin clientes.editar solo se
    puede dar el rol con los valores por defecto (sin cupo)."""
    actual = conn.execute("SELECT * FROM clientes WHERE tercero_id = %s", (tercero_id,)).fetchone()
    base = actual or {"limite_credito": 0, "dias_credito": DIAS_CREDITO_POR_DEFECTO, "activo": True}
    cambios = {k: v for k, v in datos.items() if k in base and base[k] != v}
    if cambios and not actor.puede(PERMISO_CLIENTES):
        raise SinPermiso("Cambiar el cupo, los días de crédito o el estado de un cliente requiere permiso de clientes.")
    if actual is None:
        valores = {**base, **cambios}
        conn.execute(
            "INSERT INTO clientes (tercero_id, limite_credito, dias_credito, activo) VALUES (%s, %s, %s, %s)",
            (tercero_id, valores["limite_credito"], valores["dias_credito"], valores["activo"]),
        )
        auditar(conn, actor.id, "cliente",
                f"Registró como cliente a {nombre} (cupo ${valores['limite_credito']}, {valores['dias_credito']} días)",
                "terceros", tercero_id)
    elif cambios:
        actualizar(conn, "clientes", tercero_id, cambios, pk="tercero_id")
        detalle = "; ".join(f"{k}: {actual[k]} → {v}" for k, v in cambios.items())
        auditar(conn, actor.id, "cliente", f"Editó el cliente {nombre}: {detalle}", "terceros", tercero_id)


def _rol_proveedor(conn, actor: Usuario, tercero_id, nombre: str, datos: dict) -> None:
    if not actor.puede(PERMISO_PROVEEDORES):
        raise SinPermiso("Registrar o editar proveedores requiere permiso de compras.")
    actual = conn.execute("SELECT * FROM proveedores WHERE tercero_id = %s", (tercero_id,)).fetchone()
    if actual is None:
        conn.execute("INSERT INTO proveedores (tercero_id, contacto, activo) VALUES (%s, %s, %s)",
                     (tercero_id, datos.get("contacto"), datos.get("activo", True)))
        auditar(conn, actor.id, "compra", f"Registró como proveedor a {nombre}", "terceros", tercero_id)
        return
    cambios = {k: v for k, v in datos.items() if k in ("contacto", "activo") and actual[k] != v}
    if cambios:
        actualizar(conn, "proveedores", tercero_id, cambios, pk="tercero_id")
        detalle = "; ".join(f"{k}: {actual[k]} → {v}" for k, v in cambios.items())
        auditar(conn, actor.id, "compra", f"Editó el proveedor {nombre}: {detalle}", "terceros", tercero_id)
