"""
Modelo InfoCursada — información del cursado cargada por el profesor.
Incluye condiciones de aprobación, cantidad de parciales, TFI, etc.
Un registro por cursada (upsert). Se muestra a alumnos de esa comisión.
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InfoCursada(Base):
    __tablename__ = "info_cursada"
    __table_args__ = (
        # Un solo registro de info por cursada
        UniqueConstraint("cursada_id", name="uq_info_cursada"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    cursada_id: Mapped[int] = mapped_column(ForeignKey("cursadas.id"), nullable=False, index=True)

    # Información general del cursado
    condiciones_aprobacion: Mapped[str | None] = mapped_column(Text)
    cantidad_parciales: Mapped[int | None] = mapped_column()
    tiene_tfi: Mapped[bool | None] = mapped_column(default=False)
    descripcion_tfi: Mapped[str | None] = mapped_column(Text)
    modalidad_cursado: Mapped[str | None] = mapped_column(String(200))
    # Campo libre para cualquier info adicional (fechas tentativas, condiciones especiales, etc.)
    info_adicional: Mapped[str | None] = mapped_column(Text)

    cargado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    cursada: Mapped["Cursada"] = relationship("Cursada")
    autor: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[cargado_por])

    def __repr__(self) -> str:
        return f"<InfoCursada cursada={self.cursada_id}>"
