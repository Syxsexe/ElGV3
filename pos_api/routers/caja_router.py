"""pos_api/routers/caja_router.py — solo lectura para el piloto.

Abrir/cerrar caja se queda en el desktop por ahora (fuera de alcance del
piloto de Ventas/Cuentas); la web solo necesita saber si hay una sesión
abierta para permitir cobrar cuentas.
"""
from fastapi import APIRouter, Depends

from modules.caja import get_sesion_activa, hay_sesion_abierta
from pos_api.security import usuario_actual

router = APIRouter(prefix="/caja", tags=["caja"], dependencies=[Depends(usuario_actual)])


@router.get("/sesion-activa")
def get_caja_sesion_activa():
    return {"abierta": hay_sesion_abierta(), "sesion": get_sesion_activa()}
