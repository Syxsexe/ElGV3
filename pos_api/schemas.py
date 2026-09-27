"""pos_api/schemas.py — modelos Pydantic de request/response del piloto."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    usuario: str
    contrasena: str


class LoginResponse(BaseModel):
    token: str
    usuario: str
    rol: str


class AbrirCuentaRequest(BaseModel):
    cliente: str
    mesa: str
    notas: str | None = None
    cliente_id: int | None = None


class AgregarItemRequest(BaseModel):
    producto_id: int | None = None
    combo_id: int | None = None
    insumo_id: int | None = None
    cantidad: float = Field(default=1, gt=0)


class CambiarCantidadRequest(BaseModel):
    cantidad: float = Field(gt=0)


class PagoMixto(BaseModel):
    metodo: str
    monto: float = Field(gt=0)


class CobrarCuentaRequest(BaseModel):
    metodo_pago: str = "efectivo"
    descuento: float = Field(default=0, ge=0)
    pagos: list[PagoMixto] | None = None


class ItemCarrito(BaseModel):
    tipo: Literal["producto", "combo", "adicional"]
    id: int
    cantidad: float = Field(default=1, gt=0)


class RegistrarVentaRequest(BaseModel):
    items: list[ItemCarrito]
    metodo_pago: str = "efectivo"
    descuento: float = Field(default=0, ge=0)
    cliente_id: int | None = None
    pagos: list[PagoMixto] | None = None


class AbrirCajaRequest(BaseModel):
    monto_base: float = Field(ge=0)
    monto_base_digital: float = Field(default=0, ge=0)
    notas: str | None = None


class CerrarCajaRequest(BaseModel):
    # Claves de denominación como string porque JSON no admite claves numéricas
    # (ej. {"50": 2, "100000": 1}); el router las convierte a int antes de
    # llamar a modules.caja.cerrar_caja.
    denominaciones: dict[str, int]
    digital: float = Field(ge=0)
    notas: str | None = None

    @field_validator("denominaciones")
    @classmethod
    def _cantidades_no_negativas(cls, v: dict[str, int]) -> dict[str, int]:
        for cantidad in v.values():
            if cantidad < 0:
                raise ValueError("Las cantidades de denominaciones no pueden ser negativas.")
        return v
