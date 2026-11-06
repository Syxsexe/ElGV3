"""
pos_api/modelos.py — Tipos comunes de los modelos Pydantic.

Plata y cantidades entran como Decimal (nunca float) con los mismos límites
que sus columnas en Postgres. De salida, FastAPI convierte Decimal a número
JSON, UUID a string y fechas a ISO 8601.
"""
from decimal import Decimal
from typing import Annotated

from pydantic import Field, StringConstraints

Dinero = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)]
DineroPositivo = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=2)]
Cantidad = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=3)]
Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
