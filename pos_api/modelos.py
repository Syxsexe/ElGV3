"""
pos_api/modelos.py — Tipos comunes de los modelos Pydantic.

Plata y cantidades entran como Decimal (nunca float) con los mismos límites
que sus columnas en Postgres. De salida, FastAPI convierte Decimal a número
JSON, UUID a string y fechas a ISO 8601.
"""
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, StringConstraints

Dinero = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
DineroPositivo = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
Cantidad = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]
Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
# Texto libre opcional: "" o solo espacios se guardan como NULL.
TextoOpcional = Annotated[str | None, BeforeValidator(lambda v: (v.strip() or None) if isinstance(v, str) else v)]


def cambios_enviados(modelo: BaseModel, obligatorios: set[str] | None = None) -> dict:
    """Campos que el cliente mandó en un PATCH. Un null en una columna
    obligatoria (todas, si obligatorios es None) se ignora en vez de romper la
    fila; en las opcionales significa "borrar el dato"."""
    return {k: v for k, v in modelo.model_dump(exclude_unset=True).items()
            if v is not None or (obligatorios is not None and k not in obligatorios)}
