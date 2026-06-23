import uuid
from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.database import Base


class SyncLog(Base):
    """Registro de sincronización entre desktop y cloud"""

    __tablename__ = "sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uuid_operacion: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    entidad_tipo: Mapped[str] = mapped_column(
        SAEnum(
            "venta", "factura", "dee_pos", "nota_credito", "nota_debito",
            "cliente", "producto", "caja",
            name="sync_entidad_enum",
        ),
        nullable=False,
    )
    entidad_id_local: Mapped[int] = mapped_column(Integer, nullable=False)
    accion: Mapped[str] = mapped_column(
        SAEnum("crear", "actualizar", "anular", name="sync_accion_enum"),
        nullable=False,
    )
    estado: Mapped[str] = mapped_column(
        SAEnum(
            "pendiente", "sincronizado", "error", "ignorado",
            name="sync_estado_enum",
        ),
        nullable=False,
        default="pendiente",
    )
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    resultado: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    creado_en: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    sincronizado_en: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self):
        return f"<SyncLog {self.entidad_tipo}#{self.entidad_id_local} [{self.estado}]>"
