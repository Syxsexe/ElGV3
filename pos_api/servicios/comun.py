"""pos_api/servicios/comun.py — Atajos compartidos por los servicios."""
import unicodedata

from psycopg import sql

from pos_api.errores import ErrorNegocio, NoEncontrado


def actualizar(conn, tabla: str, id_, cambios: dict, *, pk: str = "id", no_existe: str = "No existe.") -> dict:
    """UPDATE de las columnas de `cambios` (ya validadas por quien llama) en la
    fila `id_`; retorna la fila resultante. Sin cambios, solo la lee."""
    if cambios:
        consulta = sql.SQL("UPDATE {} SET {} WHERE {} = %(_id)s RETURNING *").format(
            sql.Identifier(tabla),
            sql.SQL(", ").join(
                sql.SQL("{} = {}").format(sql.Identifier(c), sql.Placeholder(c)) for c in cambios),
            sql.Identifier(pk),
        )
    else:
        consulta = sql.SQL("SELECT * FROM {} WHERE {} = %(_id)s").format(sql.Identifier(tabla), sql.Identifier(pk))
    fila = conn.execute(consulta, {**cambios, "_id": id_}).fetchone()
    if fila is None:
        raise NoEncontrado(no_existe)
    return fila


def describir_cambios(cambios: dict) -> str:
    """Texto corto para la auditoría: 'nombre=Mesa 3, activa=False'."""
    return ", ".join(f"{k}={v}" for k, v in cambios.items())


def sin_tildes(texto: str) -> str:
    """Mayúsculas sin tildes (Ñ → N), como se comparan los nombres DIVIPOLA."""
    return "".join(c for c in unicodedata.normalize("NFD", texto.upper()) if unicodedata.category(c) != "Mn")


# Pesos del dígito de verificación del NIT (DIAN), de derecha a izquierda.
_PESOS_DV = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


def digito_verificacion(nit: str) -> int:
    """Dígito de verificación DIAN de un NIT (sin el DV)."""
    if not nit.isdigit() or len(nit) > len(_PESOS_DV):
        raise ValueError("El NIT debe tener solo dígitos (máximo 15), sin el dígito de verificación.")
    residuo = sum(int(d) * p for d, p in zip(reversed(nit), _PESOS_DV)) % 11
    return residuo if residuo < 2 else 11 - residuo


# ── Búsqueda por nombre ─────────────────────────────────────────────────────
# normalizar() (minúsculas sin tildes, en SQL) a ambos lados, y el texto del
# usuario como literal: sus % y _ no son comodines.

def condicion_busqueda(columna: str) -> str:
    """Condición SQL para `columna` contiene el texto buscado; va con
    {"patron": literal_like(texto)} en los parámetros. `columna` es fija del
    código, nunca del cliente."""
    return f"normalizar({columna}) LIKE '%%' || normalizar(%(patron)s) || '%%'"


def literal_like(texto: str | None) -> str | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ── Documentos de identidad ─────────────────────────────────────────────────

# Registro civil, tarjeta de identidad, cédula, NIT y NUIP llevan solo dígitos.
SOLO_DIGITOS = {"11", "12", "13", "31", "91"}


def limpiar_numero(numero: str | None) -> str:
    """Sin puntos ni espacios: "1.085.123 456" → "1085123456"."""
    return (numero or "").replace(".", "").replace(" ", "").strip()


def normalizar_documento(tipo: str | None, numero: str | None) -> str | None:
    """Limpia el número y lo valida según el tipo (código DIAN). Un NIT escrito
    con su DV ("900123456-8") se acepta si el DV es correcto y se guarda sin él."""
    numero = limpiar_numero(numero)
    if tipo is None:
        if numero:
            raise ErrorNegocio("Elige el tipo de documento o deja el número vacío.")
        return None
    if not numero:
        raise ErrorNegocio("Falta el número de documento.")
    if tipo == "31" and "-" in numero:
        numero, dv = numero.rsplit("-", 1)
        if not (numero.isdigit() and dv.isdigit()):
            raise ErrorNegocio("El NIT lleva solo dígitos (y el dígito de verificación después del guion).")
        if int(dv) != digito_verificacion(numero):
            raise ErrorNegocio(f"El dígito de verificación no coincide: para el NIT {numero} es {digito_verificacion(numero)}.")
    if tipo in SOLO_DIGITOS and not numero.isdigit():
        raise ErrorNegocio("Este tipo de documento lleva solo dígitos.")
    if tipo == "31":
        try:
            digito_verificacion(numero)
        except ValueError as exc:
            raise ErrorNegocio(str(exc)) from exc
    return numero


def tipo_identificacion_id(conn, codigo: str | None):
    """id del tipo de documento por su código DIAN (None → None)."""
    if codigo is None:
        return None
    fila = conn.execute("SELECT id FROM tipos_identificacion WHERE codigo = %s", (codigo,)).fetchone()
    if fila is None:
        raise ErrorNegocio("Tipo de documento desconocido.")
    return fila["id"]
