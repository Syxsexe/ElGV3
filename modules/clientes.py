"""
modules/clientes.py — El G POS
Gestión de clientes para facturación y clientes frecuentes.
"""

from database import get_connection

TIPOS_DOCUMENTO = ("CC", "NIT", "CE", "TI", "CONSUMIDOR_FINAL")


def listar_clientes(solo_activos: bool = True) -> list:
    """Retorna los clientes registrados."""
    conn = get_connection()
    query = "SELECT * FROM clientes"
    params = []
    if solo_activos:
        query += " WHERE activo = 1"
    query += " ORDER BY nombre"
    filas = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def buscar_clientes(texto: str) -> list:
    """Busca clientes por nombre, documento o teléfono."""
    conn = get_connection()
    texto = f"%{texto}%"
    filas = conn.execute(
        "SELECT * FROM clientes"
        " WHERE activo = 1"
        "   AND (nombre LIKE ? OR documento LIKE ? OR telefono LIKE ?)",
        (texto, texto, texto)
    ).fetchall()
    conn.close()
    return [dict(f) for f in filas]


def obtener_cliente(cliente_id: int) -> dict | None:
    """Retorna un cliente por su ID."""
    conn = get_connection()
    fila = conn.execute(
        "SELECT * FROM clientes WHERE id = ?", (cliente_id,)
    ).fetchone()
    conn.close()
    return dict(fila) if fila else None


def crear_cliente(
    nombre: str,
    tipo_documento: str,
    documento: str,
    direccion: str = None,
    telefono: str = None,
    email: str = None
) -> int:
    """Crea un cliente nuevo y retorna su ID."""
    nombre = nombre.strip()
    tipo_documento = tipo_documento.strip().upper()
    documento = documento.strip()

    if not nombre:
        raise ValueError("El nombre del cliente es obligatorio.")
    if tipo_documento not in TIPOS_DOCUMENTO:
        raise ValueError(f"Tipo de documento inválido: {tipo_documento}.")
    if not documento:
        raise ValueError("El documento es obligatorio.")

    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO clientes
                (nombre, tipo_documento, documento, direccion, telefono, email)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nombre, tipo_documento, documento, direccion, telefono, email)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def editar_cliente(cliente_id: int, **campos) -> bool:
    """Edita los datos de un cliente."""
    permitidos = {
        "nombre", "tipo_documento", "documento",
        "direccion", "telefono", "email", "activo"
    }
    campos_validos = {k: v for k, v in campos.items() if k in permitidos}
    if not campos_validos:
        return False

    if "tipo_documento" in campos_validos:
        tipo_documento = str(campos_validos["tipo_documento"]).strip().upper()
        if tipo_documento not in TIPOS_DOCUMENTO:
            raise ValueError(f"Tipo de documento inválido: {tipo_documento}.")
        campos_validos["tipo_documento"] = tipo_documento

    if "nombre" in campos_validos:
        campos_validos["nombre"] = str(campos_validos["nombre"]).strip()
    if "documento" in campos_validos:
        campos_validos["documento"] = str(campos_validos["documento"]).strip()

    set_clause = ", ".join(f"{k} = ?" for k in campos_validos)
    valores = list(campos_validos.values()) + [cliente_id]

    conn = get_connection()
    try:
        conn.execute(f"UPDATE clientes SET {set_clause} WHERE id = ?", valores)
        conn.commit()
        return True
    finally:
        conn.close()
