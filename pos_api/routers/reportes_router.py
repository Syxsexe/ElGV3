"""pos_api/routers/reportes_router.py — tablero de Inicio y reportes.

Inicio: cualquier usuario con sesión (lo que se le debe a proveedores solo
con compras.registrar). Reportes por rango: reportes.ver.
"""
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from pos_api.db import transaccion
from pos_api.seguridad import Usuario, requiere_permiso, usuario_actual
from pos_api.servicios import reportes as servicio

router = APIRouter(tags=["reportes"])
lector = requiere_permiso("reportes.ver")


@router.get("/inicio")
def get_inicio(actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.inicio(conn, actor)


@router.get("/reportes/ventas")
def get_ventas(desde: date, hasta: date, q: Annotated[str | None, Query(max_length=100)] = None,
               limite: Annotated[int, Query(ge=1, le=200)] = 100, desde_fila: Annotated[int, Query(ge=0)] = 0,
               _: Usuario = Depends(lector)):
    with transaccion() as conn:
        return servicio.ventas_del_rango(conn, desde, hasta, texto=q, limite=limite, desplazamiento=desde_fila)


@router.get("/reportes")
def get_reporte(desde: date, hasta: date, _: Usuario = Depends(lector)):
    with transaccion() as conn:
        return servicio.reporte(conn, desde, hasta)
