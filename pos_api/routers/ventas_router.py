"""pos_api/routers/ventas_router.py — venta directa (carrito), envuelve modules/ventas.py."""
from fastapi import APIRouter, Depends

from modules.caja import get_sesion_activa
from modules.ventas import Carrito, registrar_venta
from pos_api.schemas import RegistrarVentaRequest
from pos_api.security import usuario_actual

router = APIRouter(prefix="/ventas", tags=["ventas"], dependencies=[Depends(usuario_actual)])


@router.post("")
def post_registrar_venta(body: RegistrarVentaRequest):
    carrito = Carrito()
    for item in body.items:
        if item.tipo == "producto":
            carrito.agregar_producto(item.id, item.cantidad)
        elif item.tipo == "combo":
            carrito.agregar_combo(item.id, item.cantidad)
        elif item.tipo == "adicional":
            carrito.agregar_adicional(item.id, item.cantidad)
        else:
            # Inalcanzable mientras ItemCarrito.tipo sea el Literal de schemas.py;
            # queda como red de seguridad si algún día se agrega un tipo nuevo
            # ahí sin actualizar este router.
            raise ValueError(f"Tipo de ítem no soportado: {item.tipo}")

    sesion = get_sesion_activa()
    if not sesion:
        raise ValueError("No hay una caja abierta. Ábrela desde el escritorio antes de cobrar.")
    venta_id = registrar_venta(
        carrito,
        metodo_pago=body.metodo_pago,
        descuento=body.descuento,
        sesion_id=sesion["id"],
        cliente_id=body.cliente_id,
        pagos=[p.model_dump() for p in body.pagos] if body.pagos else None,
    )
    return {"venta_id": venta_id}
