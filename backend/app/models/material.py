"""
Modelo MaterialApoyo — enlaces o referencias a material de estudio
asociados a una cursada (apuntes, videos, ejercicios, etc.).
"""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TipoMaterialEnum(str, enum.Enum):
    apunte = "apunte"
    video = "video"
    ejercicio = "ejercicio"
    bibliografía = "bibliografia"
    otro = "otro"


class MaterialApoyo(Base):
    __tablename__ = "materiales_apoyo"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    cursada_id: Mapped[int] = mapped_column(ForeignKey("cursadas.id"), nullable=False, index=True)
    tipo: Mapped[TipoMaterialEnum] = mapped_column(Enum(TipoMaterialEnum), nullable=False)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str | None] = mapped_column(Text)
    descripcion: Mapped[str | None] = mapped_column(Text)

    # Quién cargó el material
    cargado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relaciones
    cursada: Mapped["Cursada"] = relationship("Cursada", back_populates="materiales")
    autor: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[cargado_por])

    def __repr__(self) -> str:
        return f"<MaterialApoyo '{self.titulo}' cursada={self.cursada_id}>"
