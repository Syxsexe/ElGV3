import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    String, Integer, Numeric, DateTime, Text, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class DEEPOS(Base):
    """Documento Equivalente Electrónico — Tiquete POS"""

    __tablename__ = "dee_pos"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resolucion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resoluciones.id"), nullable=False
    )
    prefijo: Mapped[str] = mapped_column(String(4), nullable=False)
    consecutivo: Mapped[int] = mapped_column(Integer, nullable=False)

    fecha_emision: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    fecha_transmision: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Adquiriente (opcional en DEE POS, obligatorio si > 5 UVT)
    adquiriente_nit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    adquiriente_razon_social: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Valores
    total_base: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    # DIAN
    cufe: Mapped[str | None] = mapped_column(String(96), nullable=True, unique=True)
    estado_dian: Mapped[str] = mapped_column(
        SAEnum(
            "pendiente", "enviada", "aceptada", "rechazada", "contingencia",
            name="dee_pos_estado_enum",
        ),
        nullable=False,
        default="pendiente",
    )
    mensaje_dian: Mapped[str | None] = mapped_column(Text, nullable=True)

    xml_enviado: Mapped[str | None] = mapped_column(Text, nullable=True)
    xml_recibido: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Items
    items: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Agrupación (se envían en lote)
    sesion_caja_id_local: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    venta_id_local: Mapped[int | None] = mapped_column(Integer, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    def __repr__(self):
        return f"<DEEPOS {self.prefijo}{self.consecutivo} [{self.estado_dian}]>"
