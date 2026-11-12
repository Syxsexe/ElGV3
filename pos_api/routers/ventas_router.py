"""pos_api/routers/ventas_router.py — ventas directas y cuentas por mesa.

Vender, fiar dentro del cupo del cliente y llevar cuentas lo hace cualquier
usuario con sesión (es el trabajo del mostrador). Las reglas de plata
(cuadre, turno abierto, caja en el turno) las revisa el servicio y la base.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from pos_api.db import transaccion
from pos_api.modelos import Cantidad, Dinero, DineroPositivo, TextoOpcional, cambios_enviados
from pos_api.seguridad import Usuario, usuario_actual
from pos_api.servicios import comandas, cuentas, ventas

router = APIRouter(tags=["ventas"])


class Eleccion(BaseModel):
    """La opción elegida en un grupo de un combo."""
    grupo_id: uuid.UUID
    producto_id: uuid.UUID


Elecciones = Annotated[list[Eleccion], Field(max_length=20)]


class Linea(BaseModel):
    articulo_id: uuid.UUID
    cantidad: Cantidad
    elecciones: Elecciones = []


class Pago(BaseModel):
    metodo_pago_id: uuid.UUID
    monto: DineroPositivo


class Cobro(BaseModel):
    """Cómo se paga: en el turno que el cajero tiene en pantalla."""
    sesion_id: uuid.UUID
    descuento: Dinero = 0
    pagos: Annotated[list[Pago], Field(max_length=20)] = []
    fiado: Dinero = 0
    cliente_id: uuid.UUID | None = None
    notas: TextoOpcional = None


class NuevaVenta(Cobro):
    lineas: Annotated[list[Linea], Field(min_length=1, max_length=500)]


class DatosCuenta(BaseModel):
    """A nombre de un cliente registrado o de un alias; la mesa es opcional."""
    mesa_id: uuid.UUID | None = None
    cliente_id: uuid.UUID | None = None
    alias: TextoOpcional = None
    notas: TextoOpcional = None


class NuevoItem(BaseModel):
    articulo_id: uuid.UUID
    cantidad: Cantidad = 1
    elecciones: Elecciones = []


class CambiarItem(BaseModel):
    cantidad: Cantidad


class ItemComanda(BaseModel):
    cuenta_item_id: uuid.UUID
    cantidad: Cantidad
    comentario: TextoOpcional = None


class NuevaComanda(BaseModel):
    items: Annotated[list[ItemComanda], Field(min_length=1, max_length=200)]
    notas: TextoOpcional = None


class Cancelar(BaseModel):
    motivo: TextoOpcional = None


def _cobro(body: Cobro) -> dict:
    return {"descuento": body.descuento, "pagos": [p.model_dump() for p in body.pagos], "fiado": body.fiado,
            "cliente_id": body.cliente_id, "notas": body.notas}


# ── Ventas ──────────────────────────────────────────────────────────────────

@router.post("/ventas", status_code=status.HTTP_201_CREATED)
def post_venta(body: NuevaVenta, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return ventas.registrar_venta(conn, actor, body.sesion_id, [l.model_dump() for l in body.lineas],
                                      **_cobro(body))


@router.get("/ventas/{venta_id}")
def get_venta(venta_id: uuid.UUID, _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return ventas.detalle_venta(conn, venta_id)


@router.get("/clientes/{cliente_id}/cupo")
def get_cupo(cliente_id: uuid.UUID, _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return ventas.cupo_cliente(conn, cliente_id)


# ── Cuentas ─────────────────────────────────────────────────────────────────

@router.get("/cuentas")
def get_cuentas(_: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return cuentas.listar_abiertas(conn)


@router.post("/cuentas", status_code=status.HTTP_201_CREATED)
def post_cuenta(body: DatosCuenta, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return cuentas.abrir_cuenta(conn, actor, body.mesa_id, body.cliente_id, body.alias, body.notas)


@router.get("/cuentas/{cuenta_id}")
def get_cuenta(cuenta_id: uuid.UUID, _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return cuentas.obtener_cuenta(conn, cuenta_id)


@router.patch("/cuentas/{cuenta_id}")
def patch_cuenta(cuenta_id: uuid.UUID, body: DatosCuenta, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        # mesa_id y notas admiten null (sin mesa, sin notas); cliente y alias no.
        return cuentas.editar_cuenta(conn, actor, cuenta_id, cambios_enviados(body, {"cliente_id", "alias"}))


@router.post("/cuentas/{cuenta_id}/items", status_code=status.HTTP_201_CREATED)
def post_item(cuenta_id: uuid.UUID, body: NuevoItem, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return cuentas.agregar_item(conn, actor, cuenta_id, body.articulo_id, body.cantidad,
                                    [e.model_dump() for e in body.elecciones])


@router.patch("/cuentas/{cuenta_id}/items/{item_id}")
def patch_item(cuenta_id: uuid.UUID, item_id: uuid.UUID, body: CambiarItem, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return cuentas.cambiar_cantidad(conn, actor, cuenta_id, item_id, body.cantidad)


@router.delete("/cuentas/{cuenta_id}/items/{item_id}")
def delete_item(cuenta_id: uuid.UUID, item_id: uuid.UUID, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return cuentas.quitar_item(conn, actor, cuenta_id, item_id)


@router.get("/cuentas/{cuenta_id}/comandas")
def get_comandas(cuenta_id: uuid.UUID, _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return comandas.listar_comandas(conn, cuenta_id)


@router.post("/cuentas/{cuenta_id}/comandas", status_code=status.HTTP_201_CREATED)
def post_comanda(cuenta_id: uuid.UUID, body: NuevaComanda, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return comandas.crear_comanda(conn, actor, cuenta_id, [i.model_dump() for i in body.items], body.notas)


@router.post("/cuentas/{cuenta_id}/cobrar", status_code=status.HTTP_201_CREATED)
def post_cobrar(cuenta_id: uuid.UUID, body: Cobro, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return cuentas.cobrar_cuenta(conn, actor, cuenta_id, body.sesion_id, **_cobro(body))


@router.post("/cuentas/{cuenta_id}/cancelar")
def post_cancelar(cuenta_id: uuid.UUID, body: Cancelar, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return cuentas.cancelar_cuenta(conn, actor, cuenta_id, body.motivo)
