"""pos_api/schemas.py — modelos Pydantic de request/response del piloto."""
from pydantic import BaseModel


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
    cantidad: float = 1


class CambiarCantidadRequest(BaseModel):
    cantidad: float


class PagoMixto(BaseModel):
    metodo: str
    monto: float


class CobrarCuentaRequest(BaseModel):
    metodo_pago: str = "efectivo"
    descuento: float = 0
    pagos: list[PagoMixto] | None = None
