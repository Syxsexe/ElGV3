import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Numeric, DateTime, Text, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class Factura(Base):
    __tablename__ = "facturas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable: las facturas "solo local" (no emitidas a DIAN) no dependen de
    # una resolución electrónica.
    resolucion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resoluciones.id"), nullable=True
    )
    prefijo: Mapped[str] = mapped_column(String(4), nullable=False)
    consecutivo: Mapped[int] = mapped_column(Integer, nullable=False)

    # Timestamps
    fecha_emision: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fecha_validacion_dian: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Tipo de documento DIAN
    tipo_documento: Mapped[str] = mapped_column(
        SAEnum("FEV", name="factura_tipo_enum"), nullable=False, default="FEV"
    )

    # Adquiriente
    adquiriente_nit: Mapped[str] = mapped_column(String(20), nullable=False)
    adquiriente_razon_social: Mapped[str] = mapped_column(String(300), nullable=False)
    adquiriente_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    adquiriente_direccion: Mapped[str | None] = mapped_column(String(200), nullable=True)
    adquiriente_telefono: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Valores
    total_base: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    iva_porcentaje: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=19.00)
    total_impuestos: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # DIAN
    cufe: Mapped[str | None] = mapped_column(String(96), nullable=True, unique=True)
    qr_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    estado_dian: Mapped[str] = mapped_column(
        SAEnum(
            "local", "pendiente", "enviada", "en_proceso", "aceptada", "rechazada",
            "contingencia", "anulada", "error",
            name="factura_estado_enum",
        ),
        nullable=False,
        default="pendiente",
    )
    mensaje_dian: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Proveedor Tecnológico (capa app/fe): 'matias', 'directo', 'mock'…
    proveedor: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Id de seguimiento del documento en el PT (para webhook/consulta).
    track_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    # Enlaces a la representación gráfica y XML servidos por el PT.
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    xml_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # XML almacenado
    xml_enviado: Mapped[str | None] = mapped_column(Text, nullable=True)
    xml_recibido: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Items (denormalized for DIAN tracking)
    items: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Referencia al POS local
    venta_id_local: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now, onupdate=datetime.now
    )

    def __repr__(self):
        return f"<Factura {self.prefijo}{self.consecutivo} [{self.estado_dian}]>"
