"""pos_api/routers/caja_router.py — envuelve modules/caja.py.

Abrir/cerrar caja y su historial (solo admin) se exponen aquí. La
generación del PDF de cierre (modules/reporte_caja.py) queda fuera de
alcance por ahora — sigue siendo solo de escritorio.
"""
from fastapi import APIRouter, Depends, HTTPException, status

from database import get_connection
from modules.caja import (
    abonos_sesion,
    abrir_caja,
    cerrar_caja,
    egresos_sesion,
    get_sesion_activa,
    hay_sesion_abierta,
    listar_sesiones,
    obtener_sesion,
    resumen_sesiones,
    totales_ventas_sesion,
)
from pos_api.schemas import AbrirCajaRequest, CerrarCajaRequest
from pos_api.security import usuario_actual

router = APIRouter(prefix="/caja", tags=["caja"], dependencies=[Depends(usuario_actual)])


@router.get("/sesion-activa")
def get_caja_sesion_activa():
    return {"abierta": hay_sesion_abierta(), "sesion": get_sesion_activa()}


@router.post("/abrir", status_code=status.HTTP_201_CREATED)
def post_abrir_caja(body: AbrirCajaRequest):
    sesion_id = abrir_caja(body.monto_base, monto_base_digital=body.monto_base_digital, notas=body.notas)
    return {"sesion_id": sesion_id}


@router.get("/preview-cierre")
def get_preview_cierre():
    """Mismos números que hoy arma a mano ui/caja.py, calculados en el
    servidor para que el frontend no duplique el SQL. Comparte una sola
    conexión entre las cuatro consultas de solo lectura en vez de abrir
    una por función — todas la aceptan opcionalmente para esto."""
    conn = get_connection()
    try:
        sesion = get_sesion_activa(conn=conn)
        if not sesion:
            raise ValueError("No hay una caja abierta.")

        ventas = totales_ventas_sesion(sesion["id"], conn=conn)
        egresos_ef, egresos_dig = egresos_sesion(sesion["id"], conn=conn)
        abonos_ef, abonos_dig = abonos_sesion(sesion["id"], conn=conn)
    finally:
        conn.close()

    monto_base_digital = sesion.get("monto_base_digital", 0) or 0
    esperado_efectivo = round(sesion["monto_base"] + ventas["efectivo"] + abonos_ef - egresos_ef, 2)
    esperado_digital = round(monto_base_digital + ventas["digital"] + abonos_dig - egresos_dig, 2)

    return {
        "sesion": sesion,
        "ventas": {"efectivo": ventas["efectivo"], "digital": ventas["digital"]},
        "egresos": {"efectivo": egresos_ef, "digital": egresos_dig},
        "abonos": {"efectivo": abonos_ef, "digital": abonos_dig},
        "esperado_efectivo": esperado_efectivo,
        "esperado_digital": esperado_digital,
    }


@router.post("/cerrar")
def post_cerrar_caja(body: CerrarCajaRequest):
    denominaciones = {int(k): v for k, v in body.denominaciones.items()}
    denominaciones["digital"] = body.digital
    return cerrar_caja(denominaciones, notas=body.notas)


@router.get("/historial")
def get_historial(desde: str | None = None, hasta: str | None = None, limite: int = 60):
    return listar_sesiones(limite=limite, fecha_inicio=desde, fecha_fin=hasta)


@router.get("/historial/resumen")
def get_historial_resumen(desde: str | None = None, hasta: str | None = None):
    return resumen_sesiones(fecha_inicio=desde, fecha_fin=hasta)


@router.get("/historial/{sesion_id}")
def get_historial_detalle(sesion_id: int):
    # obtener_sesion() ya está decorada con @requiere_admin (modules/caja.py),
    # el mismo mecanismo que listar_sesiones/resumen_sesiones — PermissionError
    # la captura el exception_handler global de pos_api/main.py (403). Ya no
    # hace falta un chequeo manual duplicado aquí.
    sesion = obtener_sesion(sesion_id)
    if sesion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sesión no encontrada.")
    return sesion
