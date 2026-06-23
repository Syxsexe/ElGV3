import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Numeric, DateTime, Text, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class NotaCredito(Base):
    __tablename__ = "notas_credito"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    factura_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("facturas.id"), nullable=False
    )
    resolucion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resoluciones.id"), nullable=False
    )
    prefijo: Mapped[str] = mapped_column(String(4), nullable=False)
    consecutivo: Mapped[int] = mapped_column(Integer, nullable=False)

    fecha_emision: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)

    total_base: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    cude: Mapped[str | None] = mapped_column(String(96), nullable=True, unique=True)
    estado_dian: Mapped[str] = mapped_column(
        SAEnum(
            "pendiente", "enviada", "aceptada", "rechazada", "contingencia",
            name="nc_estado_enum",
        ),
        nullable=False,
        default="pendiente",
    )
    mensaje_dian: Mapped[str | None] = mapped_column(Text, nullable=True)

    xml_enviado: Mapped[str | None] = mapped_column(Text, nullable=True)
    xml_recibido: Mapped[str | None] = mapped_column(Text, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    def __repr__(self):
        return f"<NotaCredito {self.prefijo}{self.consecutivo} [{self.estado_dian}]>"
