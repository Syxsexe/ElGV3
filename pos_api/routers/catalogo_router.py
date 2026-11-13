"""pos_api/routers/catalogo_router.py — artículos, categorías, insumos y preparaciones.

Consultar precios (/catalogo/vendibles) es para cualquier usuario con sesión
y no muestra costos. El catálogo completo, con costos, es para quien edita
inventario, combos o preparaciones.
"""
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, model_validator

from pos_api.db import transaccion
from pos_api.modelos import (Cantidad, CantidadNoNegativa, CostoUnitario, Dinero, Stock, Texto,
                             TextoOpcional, cambios_enviados)
from pos_api.seguridad import Usuario, requiere_alguno, requiere_permiso, usuario_actual
from pos_api.servicios import catalogo as servicio
from pos_api.servicios import conteo
from pos_api.servicios import importacion

router = APIRouter(prefix="/catalogo", tags=["catalogo"])
inventario = requiere_permiso(servicio.PERMISO_INVENTARIO)
preparaciones = requiere_permiso(servicio.PERMISO_PREPARACIONES)
lector = requiere_alguno(servicio.PERMISO_INVENTARIO, servicio.PERMISO_COMBOS, servicio.PERMISO_PREPARACIONES)
editor_articulos = requiere_alguno(servicio.PERMISO_INVENTARIO, servicio.PERMISO_COMBOS)
productor = requiere_alguno(servicio.PERMISO_INVENTARIO, servicio.PERMISO_PREPARACIONES)

TipoArticulo = Literal["producto", "combo", "adicional", "servicio"]


class Componente(BaseModel):
    producto_id: uuid.UUID
    cantidad: Cantidad


class OpcionCombo(BaseModel):
    producto_id: uuid.UUID
    recargo: Dinero = Decimal(0)


class GrupoCombo(BaseModel):
    """Un grupo del que se elige una opción al vender (ej. "Bebida")."""
    nombre: Texto
    cantidad: Cantidad = Decimal(1)
    # Sin min_length: un grupo vacío lo rechaza _validar_grupos con un mensaje claro.
    opciones: Annotated[list[OpcionCombo], Field(max_length=100)]


class LineaPreparacion(BaseModel):
    insumo_id: uuid.UUID
    cantidad: Cantidad


class LineaReceta(BaseModel):
    """Una línea de la receta de un plato: un insumo (o preparación) o un producto de tienda."""
    insumo_id: uuid.UUID | None = None
    producto_id: uuid.UUID | None = None
    cantidad: Cantidad

    @model_validator(mode="after")
    def _uno_de_los_dos(self):
        if (self.insumo_id is None) == (self.producto_id is None):
            raise ValueError("Cada línea de la receta es un insumo o un producto (uno de los dos).")
        return self


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
    # plato de cocina: los adicionales que acepta como toppings
    toppings: Annotated[list[uuid.UUID], Field(max_length=50)] | None = None
    # combo
    descripcion: TextoOpcional = None
    productos: list[Componente] | None = None
    grupos: Annotated[list[GrupoCombo], Field(max_length=20)] | None = None
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
    toppings: Annotated[list[uuid.UUID], Field(max_length=50)] | None = None
    descripcion: TextoOpcional = None
    productos: list[Componente] | None = None
    grupos: Annotated[list[GrupoCombo], Field(max_length=20)] | None = None
    insumo_id: uuid.UUID | None = None
    cantidad: Cantidad | None = None


# codigo y descripcion admiten null (borrar el dato); lo demás no.
_ARTICULO_OPCIONALES = {"codigo", "descripcion"}


class AjusteStock(BaseModel):
    contado: Stock
    motivo: Texto


class FilaConteo(BaseModel):
    id: uuid.UUID
    stock_visto: Stock  # el que se veía al contar: si cambió, la fila no se ajusta
    contado: CantidadNoNegativa | None = None
    stock_minimo: CantidadNoNegativa | None = None


class Conteo(BaseModel):
    filas: Annotated[list[FilaConteo], Field(min_length=1, max_length=1000)]


class Importacion(BaseModel):
    """El texto del CSV (la web lo lee del archivo). Sin confirmar es la vista previa."""
    contenido: Annotated[str, Field(min_length=1, max_length=3_000_000)]
    confirmar: bool = False


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
    stock: Stock | None = None
    stock_minimo: CantidadNoNegativa | None = None


class EditarInsumo(BaseModel):
    nombre: Texto | None = None
    unidad_medida_id: uuid.UUID | None = None
    costo_unitario: CostoUnitario | None = None
    stock_minimo: CantidadNoNegativa | None = None
    activo: bool | None = None


class GuardarPreparacion(BaseModel):
    rendimiento: Cantidad
    receta: list[LineaPreparacion]


class Produccion(BaseModel):
    lotes: Cantidad
    notas: TextoOpcional = None


class CrearPreparacion(GuardarPreparacion):
    nombre: Texto
    unidad_medida_id: uuid.UUID


def _lineas(lista: list[BaseModel] | None) -> list[dict] | None:
    return None if lista is None else [x.model_dump() for x in lista]


# ── Consulta para todos ─────────────────────────────────────────────────────

@router.get("/vendibles")
def get_vendibles(q: str | None = None, tipo: TipoArticulo | None = None,
                  categoria_tipo: Literal["tienda", "cocina"] | None = None,
                  limite: int = Query(60, ge=1, le=200), _: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.vendibles(conn, q, tipo, limite, categoria_tipo)


@router.get("/vendibles/{articulo_id}/opciones")
def get_opciones_combo(articulo_id: uuid.UUID, _: Usuario = Depends(usuario_actual)):
    """Lo que se puede elegir en un combo al venderlo (solo opciones activas, sin costos)."""
    with transaccion() as conn:
        return servicio.opciones_para_vender(conn, articulo_id)


@router.get("/vendibles/{articulo_id}/toppings")
def get_toppings_plato(articulo_id: uuid.UUID, _: Usuario = Depends(usuario_actual)):
    """Los toppings activos que acepta un plato, para elegirlos al venderlo (sin costos)."""
    with transaccion() as conn:
        return servicio.toppings_para_vender(conn, articulo_id)


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
                  activos: bool = False, categoria_tipo: Literal["tienda", "cocina"] | None = None,
                  _: Usuario = Depends(lector)):
    with transaccion() as conn:
        return servicio.listar_articulos(conn, tipo=tipo, texto=q, categoria_id=categoria_id, solo_activos=activos,
                                         categoria_tipo=categoria_tipo)


@router.get("/articulos/{articulo_id}")
def get_articulo(articulo_id: uuid.UUID, _: Usuario = Depends(lector)):
    with transaccion() as conn:
        return servicio.obtener_articulo(conn, articulo_id)


@router.post("/articulos", status_code=status.HTTP_201_CREATED)
def post_articulo(body: CrearArticulo, actor: Usuario = Depends(editor_articulos)):
    datos = body.model_dump()
    datos["receta"], datos["productos"] = _lineas(body.receta), _lineas(body.productos)
    datos["grupos"] = _lineas(body.grupos)
    with transaccion() as conn:
        return servicio.crear_articulo(conn, actor, datos)


@router.patch("/articulos/{articulo_id}")
def patch_articulo(articulo_id: uuid.UUID, body: EditarArticulo, actor: Usuario = Depends(editor_articulos)):
    cambios = cambios_enviados(body, obligatorios=set(EditarArticulo.model_fields) - _ARTICULO_OPCIONALES)
    for campo in ("receta", "productos", "grupos"):
        if campo in cambios:
            cambios[campo] = _lineas(getattr(body, campo))
    with transaccion() as conn:
        return servicio.editar_articulo(conn, actor, articulo_id, cambios)


@router.post("/articulos/{articulo_id}/ajuste-stock")
def post_ajuste_stock(articulo_id: uuid.UUID, body: AjusteStock, actor: Usuario = Depends(inventario)):
    with transaccion() as conn:
        return servicio.ajustar_stock(conn, actor, articulo_id, body.contado, body.motivo)


@router.post("/conteo/{tipo}")
def post_conteo(tipo: Literal["productos", "insumos"], body: Conteo, actor: Usuario = Depends(inventario)):
    with transaccion() as conn:
        return conteo.registrar_conteo(conn, actor, tipo, [f.model_dump() for f in body.filas])


@router.post("/importar/{tipo}")
def post_importar(tipo: Literal["productos", "insumos"], body: Importacion, actor: Usuario = Depends(inventario)):
    """Crea o actualiza productos o insumos desde un CSV: vista previa o, con
    confirmar, todo o nada (no guarda si alguna fila tiene error)."""
    with transaccion() as conn:
        return importacion.importar(conn, actor, tipo, body.contenido, body.confirmar)


# ── Insumos y preparaciones ─────────────────────────────────────────────────

@router.get("/insumos")
def get_insumos(activos: bool = False, q: str | None = None, _: Usuario = Depends(lector)):
    with transaccion() as conn:
        return servicio.listar_insumos(conn, solo_activos=activos, texto=q)


@router.post("/insumos", status_code=status.HTTP_201_CREATED)
def post_insumo(body: CrearInsumo, actor: Usuario = Depends(inventario)):
    with transaccion() as conn:
        return servicio.crear_insumo(conn, actor, body.nombre, body.unidad_medida_id, body.costo_unitario,
                                     body.stock, body.stock_minimo)


@router.patch("/insumos/{insumo_id}")
def patch_insumo(insumo_id: uuid.UUID, body: EditarInsumo, actor: Usuario = Depends(inventario)):
    with transaccion() as conn:
        return servicio.editar_insumo(conn, actor, insumo_id, cambios_enviados(body))


@router.post("/insumos/{insumo_id}/ajuste-stock")
def post_ajuste_stock_insumo(insumo_id: uuid.UUID, body: AjusteStock, actor: Usuario = Depends(inventario)):
    with transaccion() as conn:
        return servicio.ajustar_stock_insumo(conn, actor, insumo_id, body.contado, body.motivo)


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


# Producir lo hace la cocina: basta con poder editar preparaciones o inventario.
@router.post("/preparaciones/{insumo_id}/producir", status_code=status.HTTP_201_CREATED)
def post_producir(insumo_id: uuid.UUID, body: Produccion, actor: Usuario = Depends(productor)):
    with transaccion() as conn:
        return servicio.producir(conn, actor, insumo_id, body.lotes, body.notas)


@router.get("/preparaciones/{insumo_id}/producciones")
def get_producciones(insumo_id: uuid.UUID, _: Usuario = Depends(lector)):
    with transaccion() as conn:
        return servicio.listar_producciones(conn, insumo_id)


@router.delete("/preparaciones/{insumo_id}")
def delete_preparacion(insumo_id: uuid.UUID, actor: Usuario = Depends(preparaciones)):
    with transaccion() as conn:
        servicio.quitar_preparacion(conn, actor, insumo_id)
    return {"ok": True}
