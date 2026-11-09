"""
pos_api/servicios/configuracion.py — Datos del negocio y catálogos editables.

Nada de esto se borra: lo referencian ventas, turnos y torneos viejos. Lo que
ya no se usa se desactiva y deja de ofrecerse en las pantallas.
"""
import re

from pos_api.auditoria import auditar
from pos_api.errores import ErrorNegocio, NoEncontrado
from pos_api.seguridad import Usuario
from pos_api.servicios.comun import (actualizar, describir_cambios, digito_verificacion, normalizar_documento,
                                     sin_tildes, tipo_identificacion_id)

# ── Empresa ─────────────────────────────────────────────────────────────────

CAMPOS_TERCERO_EMPRESA = {
    "tipo_persona", "nombre", "numero_identificacion", "direccion", "municipio_id",
    "telefono", "email", "responsable_iva",
}
CAMPOS_EMPRESA = {"regimen_tributario", "responsable_inc", "precios_incluyen_impuestos"}


def obtener_empresa(conn) -> dict | None:
    fila = conn.execute(
        """SELECT t.id AS tercero_id, t.tipo_persona, t.nombre, ti.codigo AS tipo_identificacion,
                  ti.nombre AS tipo_identificacion_nombre, t.numero_identificacion, t.direccion,
                  t.municipio_id, m.nombre AS municipio, d.nombre AS departamento,
                  t.telefono, t.email, t.responsable_iva,
                  e.regimen_tributario, e.responsable_inc, e.precios_incluyen_impuestos
             FROM empresa e
             JOIN terceros t ON t.id = e.tercero_id
             LEFT JOIN tipos_identificacion ti ON ti.id = t.tipo_identificacion_id
             LEFT JOIN municipios m ON m.id = t.municipio_id
             LEFT JOIN departamentos d ON d.id = m.departamento_id"""
    ).fetchone()
    if fila is not None:
        fila["dv"] = digito_verificacion(fila["numero_identificacion"]) if fila["tipo_identificacion"] == "31" else None
    return fila


def editar_empresa(conn, actor: Usuario, cambios: dict) -> dict:
    """cambios: campos del tercero del negocio (incluido tipo_identificacion
    como código DIAN) y de la fila empresa."""
    actual = conn.execute("SELECT tercero_id FROM empresa FOR UPDATE").fetchone()
    if actual is None:
        raise NoEncontrado("El negocio no está configurado: corre python -m pos_api.configurar.")
    # Solo lo que de verdad cambia (la pantalla manda el formulario completo).
    antes = obtener_empresa(conn)
    cambios = {k: v for k, v in cambios.items() if antes.get(k) != v}
    if not cambios:
        return antes
    tercero = {k: v for k, v in cambios.items() if k in CAMPOS_TERCERO_EMPRESA}
    if "tipo_identificacion" in cambios or "numero_identificacion" in cambios:
        # Mismas reglas que clientes y proveedores (NIT con o sin DV, solo dígitos…).
        tipo = cambios.get("tipo_identificacion", antes["tipo_identificacion"])
        tercero["tipo_identificacion_id"] = tipo_identificacion_id(conn, tipo)
        tercero["numero_identificacion"] = normalizar_documento(
            tipo, cambios.get("numero_identificacion", antes["numero_identificacion"]))
    actualizar(conn, "terceros", actual["tercero_id"], tercero)
    actualizar(conn, "empresa", True, {k: v for k, v in cambios.items() if k in CAMPOS_EMPRESA})
    auditar(conn, actor.id, "sistema", f"Editó los datos del negocio: {describir_cambios(cambios)}",
            "terceros", actual["tercero_id"])
    return obtener_empresa(conn)


def tipos_identificacion(conn) -> list[dict]:
    return conn.execute("SELECT codigo, nombre FROM tipos_identificacion ORDER BY codigo").fetchall()


def buscar_municipios(conn, texto: str) -> list[dict]:
    """Por código DIVIPOLA o por nombre, sin importar tildes ni mayúsculas."""
    return conn.execute(
        """SELECT m.id, m.codigo, m.nombre, d.nombre AS departamento
             FROM municipios m JOIN departamentos d ON d.id = m.departamento_id
            WHERE m.codigo = %s OR translate(m.nombre, 'ÁÉÍÓÚÜÑ', 'AEIOUUN') LIKE %s
            ORDER BY m.nombre, d.nombre LIMIT 20""",
        (texto.strip(), f"%{sin_tildes(texto.strip())}%"),
    ).fetchall()


# ── Cajas y métodos de pago ─────────────────────────────────────────────────

def listar_cajas(conn) -> list[dict]:
    return conn.execute(
        """SELECT c.id, c.nombre, c.usa_denominaciones, c.activo,
                  COALESCE(json_agg(json_build_object(
                      'id', m.id, 'codigo', m.codigo, 'nombre', m.nombre, 'activo', m.activo)
                      ORDER BY m.activo DESC, m.nombre) FILTER (WHERE m.id IS NOT NULL), '[]') AS metodos
             FROM cajas c
             LEFT JOIN metodos_pago m ON m.caja_id = c.id
            GROUP BY c.id
            ORDER BY c.activo DESC, c.usa_denominaciones DESC, c.nombre"""
    ).fetchall()


def crear_caja(conn, actor: Usuario, nombre: str, usa_denominaciones: bool) -> dict:
    fila = conn.execute(
        "INSERT INTO cajas (nombre, usa_denominaciones) VALUES (%s, %s) RETURNING *",
        (nombre, usa_denominaciones),
    ).fetchone()
    auditar(conn, actor.id, "sistema", f"Creó la caja {nombre}", "cajas", fila["id"])
    return fila


def editar_caja(conn, actor: Usuario, caja_id, cambios: dict) -> dict:
    """cambios: nombre, usa_denominaciones y/o activo. Contar en billetes o
    activar/desactivar una caja cambia cómo se cierra el turno: solo con la
    caja fuera de un turno abierto."""
    if ("usa_denominaciones" in cambios or "activo" in cambios) and conn.execute(
            """SELECT EXISTS (SELECT 1 FROM sesiones_caja s JOIN sesion_cajas sc ON sc.sesion_id = s.id
                               WHERE s.cerrada_en IS NULL AND sc.caja_id = %s) AS hay""",
            (caja_id,)).fetchone()["hay"]:
        raise ErrorNegocio("La caja está en el turno abierto: ciérralo antes de cambiar cómo se cuenta o de desactivarla.")
    if cambios.get("activo") is False and conn.execute(
            "SELECT EXISTS (SELECT 1 FROM metodos_pago WHERE caja_id = %s AND activo) AS hay",
            (caja_id,)).fetchone()["hay"]:
        raise ErrorNegocio("La caja tiene métodos de pago activos: desactívalos primero.")
    fila = actualizar(conn, "cajas", caja_id, cambios, no_existe="La caja no existe.")
    auditar(conn, actor.id, "sistema", f"Editó la caja {fila['nombre']}: {describir_cambios(cambios)}",
            "cajas", caja_id)
    return fila


def _codigo_de(conn, nombre: str) -> str:
    """'Tarjeta Débito' → 'tarjeta_debito'. El código no cambia al renombrar,
    así que si ya existe (ej. el método viejo que se reemplaza) se numera."""
    base = re.sub(r"[^a-z0-9]+", "_", sin_tildes(nombre).lower()).strip("_")
    if not base:
        raise ErrorNegocio("El nombre del método necesita letras o números.")
    usados = {r["codigo"] for r in conn.execute(
        "SELECT codigo FROM metodos_pago WHERE codigo = %s OR codigo LIKE %s", (base, base + "\\_%"))}
    codigo, n = base, 1
    while codigo in usados:
        n += 1
        codigo = f"{base}_{n}"
    return codigo


def _exigir_caja_activa(conn, caja_id) -> None:
    caja = conn.execute("SELECT activo FROM cajas WHERE id = %s", (caja_id,)).fetchone()
    if caja is None:
        raise NoEncontrado("La caja no existe.")
    if not caja["activo"]:
        raise ErrorNegocio("La caja está desactivada: actívala o elige otra.")


def crear_metodo(conn, actor: Usuario, nombre: str, caja_id) -> dict:
    _exigir_caja_activa(conn, caja_id)
    codigo = _codigo_de(conn, nombre)
    fila = conn.execute(
        "INSERT INTO metodos_pago (codigo, nombre, caja_id) VALUES (%s, %s, %s) RETURNING *",
        (codigo, nombre, caja_id),
    ).fetchone()
    auditar(conn, actor.id, "sistema", f"Creó el método de pago {nombre}", "metodos_pago", fila["id"])
    return fila


def editar_metodo(conn, actor: Usuario, metodo_id, cambios: dict) -> dict:
    """cambios: nombre, caja_id y/o activo. El código no cambia (lo usan
    reportes e integraciones); la caja no cambia si ya hay pagos (0016)."""
    actual = conn.execute("SELECT caja_id FROM metodos_pago WHERE id = %s", (metodo_id,)).fetchone()
    if actual is None:
        raise NoEncontrado("El método de pago no existe.")
    if "caja_id" in cambios or cambios.get("activo") is True:
        _exigir_caja_activa(conn, cambios.get("caja_id") or actual["caja_id"])
    fila = actualizar(conn, "metodos_pago", metodo_id, cambios, no_existe="El método de pago no existe.")
    auditar(conn, actor.id, "sistema", f"Editó el método de pago {fila['nombre']}: {describir_cambios(cambios)}",
            "metodos_pago", metodo_id)
    return fila


def metodos_activos(conn) -> list[dict]:
    """Los métodos que se ofrecen al cobrar, con su caja."""
    return conn.execute(
        """SELECT m.id, m.codigo, m.nombre, m.caja_id, c.nombre AS caja, c.usa_denominaciones
             FROM metodos_pago m JOIN cajas c ON c.id = m.caja_id
            WHERE m.activo AND c.activo
            ORDER BY c.usa_denominaciones DESC, m.nombre"""
    ).fetchall()


# ── Catálogos simples: mesas, categorías de gasto, juegos ───────────────────

# nombre en la URL → (tabla, columna de "activo"). Lista cerrada: el nombre de
# la tabla nunca sale de lo que manda el cliente.
CATALOGOS = {
    "mesas": ("mesas", "activa"),
    "categorias-gasto": ("categorias_gasto", "activa"),
    "juegos": ("juegos", "activo"),
}
_ENTIDAD = {"mesas": "la mesa", "categorias-gasto": "la categoría de gasto", "juegos": "el juego"}


def _catalogo(nombre: str) -> tuple[str, str]:
    if nombre not in CATALOGOS:
        raise NoEncontrado("Catálogo desconocido.")
    return CATALOGOS[nombre]


def listar_catalogo(conn, catalogo: str, solo_activos: bool) -> list[dict]:
    tabla, activo = _catalogo(catalogo)
    filtro = f"WHERE {activo}" if solo_activos else ""
    # length() primero: las mesas "2" y "10" quedan en orden numérico.
    return conn.execute(
        f"SELECT id, nombre, {activo} AS activo FROM {tabla} {filtro} "
        f"ORDER BY {activo} DESC, length(nombre), nombre"
    ).fetchall()


def crear_en_catalogo(conn, actor: Usuario, catalogo: str, nombre: str) -> dict:
    tabla, activo = _catalogo(catalogo)
    fila = conn.execute(
        f"INSERT INTO {tabla} (nombre) VALUES (%s) RETURNING id, nombre, {activo} AS activo", (nombre,)
    ).fetchone()
    auditar(conn, actor.id, "sistema", f"Creó {_ENTIDAD[catalogo]} {nombre}", tabla, fila["id"])
    return fila


def editar_en_catalogo(conn, actor: Usuario, catalogo: str, id_, cambios: dict) -> dict:
    """cambios: nombre y/o activo (se guarda en la columna activo/activa de la tabla)."""
    tabla, activo = _catalogo(catalogo)
    columnas = {(activo if k == "activo" else k): v for k, v in cambios.items()}
    fila = actualizar(conn, tabla, id_, columnas, no_existe=f"No existe {_ENTIDAD[catalogo]}.")
    auditar(conn, actor.id, "sistema", f"Editó {_ENTIDAD[catalogo]} {fila['nombre']}: {describir_cambios(cambios)}",
            tabla, id_)
    return {"id": fila["id"], "nombre": fila["nombre"], "activo": fila[activo]}
