"""pos_api/routers/cuentas_router.py — envuelve modules/cuentas.py."""
from fastapi import APIRouter, Depends, HTTPException, status

from modules.caja import get_sesion_activa
from modules.cuentas import (
    abrir_cuenta,
    agregar_item,
    cambiar_cantidad_item,
    cancelar_cuenta,
    cobrar_cuenta,
    listar_cuentas_abiertas,
    obtener_cuenta,
    quitar_item,
    siguiente_mesa,
)
from pos_api.schemas import (
    AbrirCuentaRequest,
    AgregarItemRequest,
    CambiarCantidadRequest,
    CobrarCuentaRequest,
)
from pos_api.security import usuario_actual

router = APIRouter(prefix="/cuentas", tags=["cuentas"], dependencies=[Depends(usuario_actual)])


@router.get("")
def get_cuentas_abiertas():
    return listar_cuentas_abiertas()


@router.get("/siguiente-mesa")
def get_siguiente_mesa():
    return {"mesa": siguiente_mesa()}


@router.post("", status_code=status.HTTP_201_CREATED)
def post_abrir_cuenta(body: AbrirCuentaRequest):
    cuenta_id = abrir_cuenta(body.cliente, body.mesa, notas=body.notas, cliente_id=body.cliente_id)
    return {"id": cuenta_id}


@router.get("/{cuenta_id}")
def get_cuenta(cuenta_id: int):
    cuenta = obtener_cuenta(cuenta_id)
    if cuenta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cuenta no encontrada.")
    return cuenta


@router.post("/{cuenta_id}/items", status_code=status.HTTP_201_CREATED)
def post_agregar_item(cuenta_id: int, body: AgregarItemRequest):
    return agregar_item(
        cuenta_id,
        producto_id=body.producto_id,
        combo_id=body.combo_id,
        insumo_id=body.insumo_id,
        cantidad=body.cantidad,
    )


@router.patch("/items/{item_id}")
def patch_cambiar_cantidad(item_id: int, body: CambiarCantidadRequest):
    ok = cambiar_cantidad_item(item_id, body.cantidad)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ítem no encontrado.")
    return {"ok": True}


@router.delete("/items/{item_id}")
def delete_item(item_id: int):
    ok = quitar_item(item_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ítem no encontrado.")
    return {"ok": True}


@router.post("/{cuenta_id}/cobrar")
def post_cobrar_cuenta(cuenta_id: int, body: CobrarCuentaRequest):
    sesion = get_sesion_activa()
    if not sesion:
        raise ValueError("No hay una caja abierta. Ábrela desde el escritorio antes de cobrar.")
    venta_id = cobrar_cuenta(
        cuenta_id,
        metodo_pago=body.metodo_pago,
        descuento=body.descuento,
        sesion_id=sesion["id"],
        pagos=[p.model_dump() for p in body.pagos] if body.pagos else None,
    )
    return {"venta_id": venta_id}


@router.post("/{cuenta_id}/cancelar")
def post_cancelar_cuenta(cuenta_id: int):
    cancelar_cuenta(cuenta_id)
    return {"ok": True}
