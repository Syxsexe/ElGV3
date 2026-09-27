"""pos_api/routers/productos_router.py — búsqueda para el modal "Agregar consumo"."""
from fastapi import APIRouter, Depends

from modules.inventario import buscar_productos
from modules.ventas import listar_combos
from pos_api.security import usuario_actual

router = APIRouter(prefix="/productos", tags=["productos"], dependencies=[Depends(usuario_actual)])


@router.get("/buscar")
def get_buscar_productos(q: str, tipo: str | None = None):
    return buscar_productos(q, tipo=tipo)


@router.get("/combos")
def get_combos():
    return listar_combos()
