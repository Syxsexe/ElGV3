"""pos_api/schemas.py — modelos Pydantic de request/response del piloto."""
from pydantic import BaseModel, Field


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
    tipo: str  # 'producto' | 'combo' | 'adicional'
    id: int
    cantidad: float = Field(default=1, gt=0)


class RegistrarVentaRequest(BaseModel):
    items: list[ItemCarrito]
    metodo_pago: str = "efectivo"
    descuento: float = Field(default=0, ge=0)
    cliente_id: int | None = None
    pagos: list[PagoMixto] | None = None
