"""
Capa de Facturación Electrónica (FE) — interfaz agnóstica de proveedor.

El POS/backend emite documentos contra la interfaz `ProveedorFE`; detrás se
enchufa un adaptador concreto (Matias API, DIAN directo, mock…). Así el día que
se cambie de Proveedor Tecnológico solo se implementa un adaptador nuevo sin
tocar ventas, notas ni la UI.

`DocumentoFE` es el documento normalizado que entra a cualquier adaptador;
`ResultadoFE` es la respuesta normalizada que devuelve. `EventoWebhook` es la
notificación entrante (webhook) ya normalizada.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

# Estados normalizados internos (independientes del proveedor).
#  - en_proceso: enviado al PT, DIAN aún validando (asíncrono).
#  - aceptada / rechazada: veredicto final de DIAN.
#  - anulada: documento anulado.
#  - error: fallo técnico (red, mapeo, credenciales…), reintentable.
Estado = Literal["en_proceso", "aceptada", "rechazada", "anulada", "error"]

TipoDocumento = Literal["factura", "nota_credito", "nota_debito"]


# ── Entrada normalizada ──────────────────────────────────────────────────────

@dataclass
class ItemFE:
    """Una línea del documento."""
    descripcion: str
    cantidad: Decimal
    precio_unit: Decimal
    subtotal: Decimal                 # cantidad * precio_unit, sin IVA
    iva_porcentaje: Decimal = Decimal("19")
    iva_valor: Decimal = Decimal("0")
    codigo: str | None = None
    unidad_id: str | None = None       # catálogo de unidades (quantity_units_id)


@dataclass
class AdquirienteFE:
    """Datos del cliente/adquiriente."""
    nit: str
    razon_social: str
    email: str | None = None
    direccion: str | None = None
    telefono: str | None = None
    # IDs de catálogo DIAN (los mapea el adaptador si vienen en None).
    tipo_documento_id: str | None = None      # identity_document_id
    tipo_organizacion_id: str | None = None   # type_organization_id (1=jurídica,2=natural)
    regimen_id: str | None = None             # tax_regime_id
    responsabilidad_id: str | None = None     # tax_level_id
    municipio_id: str | None = None           # city_id
    pais_id: str | None = None                # country_id
    codigo_postal: str | None = None


@dataclass
class DocumentoFE:
    """Documento normalizado que entra a un adaptador de proveedor."""
    tipo: TipoDocumento
    prefijo: str
    consecutivo: int
    resolucion_numero: str
    fecha_emision: datetime
    adquiriente: AdquirienteFE
    items: list[ItemFE]
    total_base: Decimal
    iva: Decimal
    total: Decimal
    descuento: Decimal = Decimal("0")
    iva_porcentaje: Decimal = Decimal("19")
    notas: str | None = None
    # Para notas crédito/débito: documento afectado + motivo.
    cufe_referencia: str | None = None
    numero_referencia: str | None = None
    fecha_referencia: str | None = None       # fecha de emisión de la factura afectada (YYYY-MM-DD)
    concepto_nota_id: str | None = None        # response_id: concepto DIAN de corrección (NC 1-6 / ND 1-4)
    motivo: str | None = None
    # Datos de pago (opcionales; el adaptador aplica defaults).
    metodo_pago_id: str | None = None         # payment_method_id (1=contado,2=crédito)
    medio_pago_id: str | None = None          # means_payment_id (10=efectivo…)
    fecha_vencimiento: str | None = None

    @property
    def numero(self) -> str:
        return f"{self.prefijo}{self.consecutivo}"


# ── Salida normalizada ───────────────────────────────────────────────────────

@dataclass
class ResultadoFE:
    """Respuesta normalizada de un adaptador tras emitir o consultar."""
    estado: Estado
    cufe: str | None = None
    track_id: str | None = None          # id del documento en el PT
    numero: str | None = None
    qr: str | None = None
    pdf_url: str | None = None
    xml_url: str | None = None
    mensaje: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.estado in ("en_proceso", "aceptada")


@dataclass
class EventoWebhook:
    """Notificación entrante (webhook) ya normalizada."""
    evento: str                          # p.ej. document.accepted
    estado: Estado
    track_id: str | None = None
    cufe: str | None = None
    numero: str | None = None
    mensaje: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


# ── Interfaz del proveedor ───────────────────────────────────────────────────

class ProveedorFE(ABC):
    """Contrato que todo Proveedor Tecnológico debe implementar."""

    nombre: str = "abstracto"

    @abstractmethod
    async def emitir(self, doc: DocumentoFE) -> ResultadoFE:
        """Emite un documento (factura, nota crédito o débito según doc.tipo)."""

    @abstractmethod
    async def consultar_estado(
        self, *, prefijo: str, consecutivo: int, track_id: str | None = None
    ) -> ResultadoFE:
        """Consulta el estado actual de un documento (respaldo del webhook)."""

    def verificar_firma_webhook(self, body: bytes, firma: str | None) -> bool:
        """Verifica la firma del webhook. Por defecto no acepta (fail-closed).

        Los adaptadores con verificación real (p.ej. HMAC) deben sobreescribir.
        """
        return False

    def parse_webhook(self, payload: dict[str, Any]) -> EventoWebhook:
        """Traduce el payload del webhook del PT a un `EventoWebhook`."""
        raise NotImplementedError

    async def verificar_conexion(self) -> dict[str, Any]:
        """Chequeo de conexión de SOLO LECTURA (no emite). {ok, status, mensaje}."""
        raise NotImplementedError
