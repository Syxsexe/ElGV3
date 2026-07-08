"""
Capa de Facturación Electrónica (FE).

`get_proveedor()` devuelve el adaptador `ProveedorFE` según `FE_PROVIDER`.
El camino legacy "directo" (genera XML/CUFE/firma/SOAP) vive todavía en
`app.services.factura_service` + `app.dian.*`; la capa `fe/` es la vía nueva y
agnóstica de proveedor (hoy: Matias API).
"""

from __future__ import annotations

from functools import lru_cache

from config import settings
from app.fe.base import (
    ProveedorFE, DocumentoFE, ItemFE, AdquirienteFE,
    ResultadoFE, EventoWebhook, Estado, TipoDocumento,
)

__all__ = [
    "ProveedorFE", "DocumentoFE", "ItemFE", "AdquirienteFE",
    "ResultadoFE", "EventoWebhook", "Estado", "TipoDocumento",
    "get_proveedor",
]


@lru_cache(maxsize=None)
def get_proveedor(nombre: str | None = None) -> ProveedorFE:
    """Devuelve el proveedor FE activo (por defecto, el de `FE_PROVIDER`)."""
    nombre = (nombre or settings.fe_provider or "directo").lower()
    if nombre == "matias":
        from app.fe.proveedores.matias import MatiasProvider
        return MatiasProvider()
    raise NotImplementedError(
        f"Proveedor FE '{nombre}' no implementado en la capa app/fe. "
        f"El camino 'directo' usa app.services.factura_service (legacy)."
    )
