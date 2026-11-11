"""pos_api/routers/compras_router.py — compras a proveedores y gastos (egresos).

Compras: todo exige compras.registrar. Egresos: un gasto lo registra
cualquier usuario con sesión (sale de la caja que opera); pagar una compra
exige compras.registrar; cruzar cuentas exige creditos.condonar (baja una
deuda sin que entre plata); anular exige gastos.anular. Ver egresos de otros
turnos (nómina, pagos a proveedores) exige reportes.ver: sin él, solo los del
turno abierto.
"""
import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, model_validator

from pos_api.db import transaccion
from pos_api.errores import SinPermiso
from pos_api.modelos import Cantidad, CostoUnitario, Dinero, DineroPositivo, Texto, TextoOpcional
from pos_api.seguridad import Usuario, requiere_permiso, usuario_actual
from pos_api.servicios import compras, egresos
from pos_api.servicios.caja import id_turno_abierto

router = APIRouter(tags=["compras y gastos"])
PERMISO_COMPRAS = "compras.registrar"
PERMISO_CRUCE = "creditos.condonar"
PERMISO_HISTORIAL = "reportes.ver"
comprador = requiere_permiso(PERMISO_COMPRAS)
anulador = requiere_permiso("gastos.anular")


class LineaCompra(BaseModel):
    producto_id: uuid.UUID | None = None
    insumo_id: uuid.UUID | None = None
    cantidad: Cantidad
    costo_unit: Annotated[CostoUnitario, Field(gt=0)]
    impuesto_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _uno_de_los_dos(self):
        if (self.producto_id is None) == (self.insumo_id is None):
            raise ValueError("Cada línea es un producto o un insumo (uno de los dos).")
        return self


class NuevaCompra(BaseModel):
    proveedor_id: uuid.UUID
    tipo_soporte: Literal["factura_electronica", "factura", "pos", "otro"] = "otro"
    numero_soporte: TextoOpcional = None
    cufe: TextoOpcional = None
    fecha_soporte: date | None = None
    notas: TextoOpcional = None
    lineas: Annotated[list[LineaCompra], Field(min_length=1, max_length=300)]


class PagoEgreso(BaseModel):
    metodo_pago_id: uuid.UUID
    monto: DineroPositivo


class NuevoEgreso(BaseModel):
    """En el turno que el cajero tiene en pantalla. Un gasto lleva categoría;
    el pago de una compra lleva compra_id."""
    sesion_id: uuid.UUID
    concepto: Texto
    compra_id: uuid.UUID | None = None
    categoria_gasto_id: uuid.UUID | None = None
    tercero_id: uuid.UUID | None = None
    pagos: Annotated[list[PagoEgreso], Field(max_length=20)] = []
    cruce: Dinero = 0
    notas: TextoOpcional = None


class Anulacion(BaseModel):
    sesion_id: uuid.UUID
    motivo: Texto


# ── Compras ─────────────────────────────────────────────────────────────────

@router.get("/compras")
def get_compras(proveedor_id: uuid.UUID | None = None, pendientes: bool = False, desde: date | None = None,
                hasta: date | None = None, _: Usuario = Depends(comprador)):
    with transaccion() as conn:
        return compras.listar_compras(conn, proveedor_id=proveedor_id, solo_pendientes=pendientes,
                                      desde=desde, hasta=hasta)


@router.get("/compras/por-pagar")
def get_por_pagar(_: Usuario = Depends(comprador)):
    with transaccion() as conn:
        return compras.por_pagar(conn)


@router.get("/compras/items")
def get_items(q: str | None = None, limite: int = Query(40, ge=1, le=200), _: Usuario = Depends(comprador)):
    with transaccion() as conn:
        return compras.items_compra(conn, q, limite)


@router.get("/compras/{compra_id}")
def get_compra(compra_id: uuid.UUID, _: Usuario = Depends(comprador)):
    with transaccion() as conn:
        return compras.detalle_compra(conn, compra_id)


@router.post("/compras", status_code=status.HTTP_201_CREATED)
def post_compra(body: NuevaCompra, actor: Usuario = Depends(comprador)):
    with transaccion() as conn:
        return compras.registrar_compra(
            conn, actor, body.proveedor_id, [l.model_dump() for l in body.lineas], tipo_soporte=body.tipo_soporte,
            numero_soporte=body.numero_soporte, cufe=body.cufe, fecha_soporte=body.fecha_soporte, notas=body.notas)


@router.delete("/compras/{compra_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_compra(compra_id: uuid.UUID, actor: Usuario = Depends(comprador)):
    with transaccion() as conn:
        compras.borrar_compra(conn, actor, compra_id)


# ── Egresos ─────────────────────────────────────────────────────────────────

@router.get("/egresos")
def get_egresos(desde: date | None = None, hasta: date | None = None, tipo: Literal["gasto", "compra"] | None = None,
                categoria_gasto_id: uuid.UUID | None = None, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        if actor.puede(PERMISO_HISTORIAL):
            return egresos.listar_egresos(conn, desde=desde, hasta=hasta, tipo=tipo,
                                          categoria_gasto_id=categoria_gasto_id)
        turno = id_turno_abierto(conn)
        if turno is None:
            return []
        return egresos.listar_egresos(conn, tipo=tipo, categoria_gasto_id=categoria_gasto_id, sesion_id=turno)


@router.get("/egresos/{egreso_id}")
def get_egreso(egreso_id: uuid.UUID, actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        egreso = egresos.detalle_egreso(conn, egreso_id)
        if not actor.puede(PERMISO_HISTORIAL) and egreso["sesion_id"] != id_turno_abierto(conn):
            raise SinPermiso("Solo puedes ver los egresos del turno abierto.")
        return egreso


@router.post("/egresos", status_code=status.HTTP_201_CREATED)
def post_egreso(body: NuevoEgreso, actor: Usuario = Depends(usuario_actual)):
    if body.compra_id is not None and not actor.puede(PERMISO_COMPRAS):
        raise SinPermiso("No tienes permiso para pagar compras.")
    if body.cruce > 0 and not actor.puede(PERMISO_CRUCE):
        raise SinPermiso("Cruzar cuentas baja una deuda de fiado: necesita el permiso de condonar.")
    with transaccion() as conn:
        return egresos.registrar_egreso(
            conn, actor, body.sesion_id, concepto=body.concepto, compra_id=body.compra_id,
            categoria_gasto_id=body.categoria_gasto_id, tercero_id=body.tercero_id,
            pagos=[p.model_dump() for p in body.pagos], cruce=body.cruce, notas=body.notas)


@router.post("/egresos/{egreso_id}/anular")
def post_anular(egreso_id: uuid.UUID, body: Anulacion, actor: Usuario = Depends(anulador)):
    with transaccion() as conn:
        return egresos.anular_egreso(conn, actor, egreso_id, body.sesion_id, body.motivo)
