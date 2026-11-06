"""pos_api/routers/catalogo_router.py — artículos, categorías, insumos y preparaciones.

Consultar precios (/catalogo/vendibles) es para cualquier usuario con sesión
y no muestra costos. El catálogo completo, con costos, es para quien edita
inventario, combos o preparaciones.
"""
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from pos_api.db import transaccion
from pos_api.modelos import (Cantidad, CantidadNoNegativa, CostoUnitario, Dinero, Stock, Texto,
                             TextoOpcional, cambios_enviados)
from pos_api.seguridad import Usuario, requiere_alguno, requiere_permiso, usuario_actual
from pos_api.servicios import catalogo as servicio

router = APIRouter(prefix="/catalogo", tags=["catalogo"])
inventario = requiere_permiso(servicio.PERMISO_INVENTARIO)
preparaciones = requiere_permiso(servicio.PERMISO_PREPARACIONES)
lector = requiere_alguno(servicio.PERMISO_INVENTARIO, servicio.PERMISO_COMBOS, servicio.PERMISO_PREPARACIONES)
editor_articulos = requiere_alguno(servicio.PERMISO_INVENTARIO, servicio.PERMISO_COMBOS)

TipoArticulo = Literal["producto", "combo", "adicional", "servicio"]


class Componente(BaseModel):
    producto_id: uuid.UUID
    cantidad: Cantidad


class LineaReceta(BaseModel):
    insumo_id: uuid.UUID
    cantidad: Cantidad


class CrearArticulo(BaseModel):
    tipo: TipoArticulo
    nombre: Texto
    categoria_id: uuid.UUID
    impuesto_id: uuid.UUID | None = None
    precio_venta: Dinero
    # producto
    codigo: TextoOpcional = None
    precio_costo: Dinero | None = None
    stock: Stock | None = None
    stock_minimo: CantidadNoNegativa | None = None
    receta: list[LineaReceta] | None = None
    # combo
    descripcion: TextoOpcional = None
    productos: list[Componente] | None = None
    # adicional
    insumo_id: uuid.UUID | None = None
    cantidad: Cantidad | None = None


class EditarArticulo(BaseModel):
    nombre: Texto | None = None
    categoria_id: uuid.UUID | None = None
    impuesto_id: uuid.UUID | None = None
    precio_venta: Dinero | None = None
    activo: bool | None = None
    codigo: TextoOpcional = None
    precio_costo: Dinero | None = None
    stock_minimo: CantidadNoNegativa | None = None
    receta: list[LineaReceta] | None = None
    descripcion: TextoOpcional = None
    productos: list[Componente] | None = None
    insumo_id: uuid.UUID | None = None
    cantidad: Cantidad | None = None


# codigo y descripcion admiten null (borrar el dato); lo demás no.
_ARTICULO_OPCIONALES = {"codigo", "descripcion"}


class AjusteStock(BaseModel):
    contado: Stock
    motivo: Texto


class CrearCategoria(BaseModel):
    nombre: Texto
    tipo: Literal["tienda", "cocina"]


class EditarCategoria(BaseModel):
    nombre: Texto | None = None
    tipo: Literal["tienda", "cocina"] | None = None


class CrearInsumo(BaseModel):
    nombre: Texto
    unidad_medida_id: uuid.UUID
    costo_unitario: CostoUnitario = 0


class EditarInsumo(BaseModel):
    nombre: Texto | None = None
    unidad_medida_id: uuid.UUID | None = None
    costo_unitario: CostoUnitario | None = None
    activo: bool | None = None


class GuardarPreparacion(BaseModel):
    rendimiento: Cantidad
    receta: list[LineaReceta]


class CrearPreparacion(GuardarPreparacion):
    nombre: Texto
    unidad_medida_id: uuid.UUID


def _lineas(lista: list[BaseModel] | None) -> list[dict] | None:
    return None if lista is None else [x.model_dump() for x in lista]


# ── Consulta para todos ─────────────────────────────────────────────────────

@router.get("/vendibles")
def get_vendibles(q: str | None = None, tipo: TipoArticulo | None = None,
                  limite: int = Query(60, ge=1, le=200), _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.vendibles(conn, q, tipo, limite)


@router.get("/categorias")
def get_categorias(_: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.listar_categorias(conn)


@router.get("/impuestos")
def get_impuestos(_: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.listar_impuestos(conn)


@router.get("/unidades")
def get_unidades(_: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.listar_unidades(conn)


# ── Categorías ──────────────────────────────────────────────────────────────

@router.post("/categorias", status_code=status.HTTP_201_CREATED)
def post_categoria(body: CrearCategoria, actor: Usuario = Depends(inventario)):
    with transaccion() as conn:
        return servicio.crear_categoria(conn, actor, body.nombre, body.tipo)


@router.patch("/categorias/{categoria_id}")
def patch_categoria(categoria_id: uuid.UUID, body: EditarCategoria, actor: Usuario = Depends(inventario)):
    with transaccion() as conn:
        return servicio.editar_categoria(conn, actor, categoria_id, cambios_enviados(body))


@router.delete("/categorias/{categoria_id}")
def delete_categoria(categoria_id: uuid.UUID, actor: Usuario = Depends(inventario)):
    with transaccion() as conn:
        servicio.borrar_categoria(conn, actor, categoria_id)
    return {"ok": True}


# ── Artículos ───────────────────────────────────────────────────────────────

@router.get("/articulos")
def get_articulos(tipo: TipoArticulo | None = None, q: str | None = None, categoria_id: uuid.UUID | None = None,
                  activos: bool = False, _: Usuario = Depends(lector)):
    with transaccion() as conn:
        return servicio.listar_articulos(conn, tipo=tipo, texto=q, categoria_id=categoria_id, solo_activos=activos)


@router.get("/articulos/{articulo_id}")
def get_articulo(articulo_id: uuid.UUID, _: Usuario = Depends(lector)):
    with transaccion() as conn:
        return servicio.obtener_articulo(conn, articulo_id)


@router.post("/articulos", status_code=status.HTTP_201_CREATED)
def post_articulo(body: CrearArticulo, actor: Usuario = Depends(editor_articulos)):
    datos = body.model_dump()
    datos["receta"], datos["productos"] = _lineas(body.receta), _lineas(body.productos)
    with transaccion() as conn:
        return servicio.crear_articulo(conn, actor, datos)


@router.patch("/articulos/{articulo_id}")
def patch_articulo(articulo_id: uuid.UUID, body: EditarArticulo, actor: Usuario = Depends(editor_articulos)):
    cambios = cambios_enviados(body, obligatorios=set(EditarArticulo.model_fields) - _ARTICULO_OPCIONALES)
    for campo in ("receta", "productos"):
        if campo in cambios:
            cambios[campo] = _lineas(getattr(body, campo))
    with transaccion() as conn:
        return servicio.editar_articulo(conn, actor, articulo_id, cambios)


@router.post("/articulos/{articulo_id}/ajuste-stock")
def post_ajuste_stock(articulo_id: uuid.UUID, body: AjusteStock, actor: Usuario = Depends(inventario)):
    with transaccion() as conn:
        return servicio.ajustar_stock(conn, actor, articulo_id, body.contado, body.motivo)


# ── Insumos y preparaciones ─────────────────────────────────────────────────

@router.get("/insumos")
def get_insumos(activos: bool = False, q: str | None = None, _: Usuario = Depends(lector)):
    with transaccion() as conn:
        return servicio.listar_insumos(conn, solo_activos=activos, texto=q)


@router.post("/insumos", status_code=status.HTTP_201_CREATED)
def post_insumo(body: CrearInsumo, actor: Usuario = Depends(inventario)):
    with transaccion() as conn:
        return servicio.crear_insumo(conn, actor, body.nombre, body.unidad_medida_id, body.costo_unitario)


@router.patch("/insumos/{insumo_id}")
def patch_insumo(insumo_id: uuid.UUID, body: EditarInsumo, actor: Usuario = Depends(inventario)):
    with transaccion() as conn:
        return servicio.editar_insumo(conn, actor, insumo_id, cambios_enviados(body))


@router.get("/preparaciones")
def get_preparaciones(_: Usuario = Depends(lector)):
    with transaccion() as conn:
        return servicio.listar_preparaciones(conn)


@router.post("/preparaciones", status_code=status.HTTP_201_CREATED)
def post_preparacion(body: CrearPreparacion, actor: Usuario = Depends(preparaciones)):
    with transaccion() as conn:
        return servicio.crear_preparacion(conn, actor, body.nombre, body.unidad_medida_id, body.rendimiento,
                                          _lineas(body.receta))


@router.put("/preparaciones/{insumo_id}")
def put_preparacion(insumo_id: uuid.UUID, body: GuardarPreparacion, actor: Usuario = Depends(preparaciones)):
    with transaccion() as conn:
        return servicio.guardar_preparacion(conn, actor, insumo_id, body.rendimiento, _lineas(body.receta))


@router.delete("/preparaciones/{insumo_id}")
def delete_preparacion(insumo_id: uuid.UUID, actor: Usuario = Depends(preparaciones)):
    with transaccion() as conn:
        servicio.quitar_preparacion(conn, actor, insumo_id)
    return {"ok": True}
