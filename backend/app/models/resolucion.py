import uuid
from datetime import date, datetime

from sqlalchemy import String, Integer, Date, DateTime, Boolean, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Resolucion(Base):
    __tablename__ = "resoluciones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Número de resolución de facturación DIAN (p.ej. "18760000001").
    # Requerido por el PT (Matias: resolution_number).
    numero_resolucion: Mapped[str | None] = mapped_column(String(30), nullable=True)
    prefijo: Mapped[str] = mapped_column(String(4), nullable=False)
    tipo_documento: Mapped[str] = mapped_column(
        SAEnum("FEV", "DEE_POS", "NC", "ND", name="tipo_documento_enum"),
        nullable=False,
    )
    rango_inicio: Mapped[int] = mapped_column(Integer, nullable=False)
    rango_fin: Mapped[int] = mapped_column(Integer, nullable=False)
    consecutivo_actual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fecha_autorizacion: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)
    clave_tecnica: Mapped[str] = mapped_column(Text, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    def __repr__(self):
        return f"<Resolucion {self.prefijo} [{self.rango_inicio}-{self.rango_fin}]>"

    @property
    def agotado(self) -> bool:
        return self.consecutivo_actual >= self.rango_fin

    @property
    def vencida(self) -> bool:
        return date.today() > self.fecha_vencimiento
