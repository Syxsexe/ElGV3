"""pos_api/routers/reportes_router.py — tablero de Inicio y reportes.

Inicio: cualquier usuario con sesión (lo que se le debe a proveedores solo
con compras.registrar). Reportes por rango: reportes.ver.
"""
from datetime import date

from fastapi import APIRouter, Depends

from pos_api.db import transaccion
from pos_api.seguridad import Usuario, requiere_permiso, usuario_actual
from pos_api.servicios import reportes as servicio

router = APIRouter(tags=["reportes"])
lector = requiere_permiso("reportes.ver")


@router.get("/inicio")
def get_inicio(actor: Usuario = Depends(usuario_actual)):
    with transaccion() as conn:
        return servicio.inicio(conn, actor)


@router.get("/reportes")
def get_reporte(desde: date, hasta: date, _: Usuario = Depends(lector)):
    with transaccion() as conn:
        return servicio.reporte(conn, desde, hasta)
