"""pos_api/servicios/comun.py — Atajos compartidos por los servicios."""
import unicodedata

from psycopg import sql

from pos_api.errores import NoEncontrado


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
