"""
Modelo Sugerencia — dato que propone cualquier usuario para sumar a la base.
Un MOD la acepta (entra como publicación de la fuente «Sugerencias de usuarios»
y queda buscable en el chat) o la rechaza con un motivo.
"""
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EstadoSugerenciaEnum(str, enum.Enum):
    PENDIENTE = "PENDIENTE"
    ACEPTADA  = "ACEPTADA"
    RECHAZADA = "RECHAZADA"


class Sugerencia(Base):
    __tablename__ = "sugerencias"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False, index=True)
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)
    contenido: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000))  # de dónde sale el dato, si hay
    estado: Mapped[EstadoSugerenciaEnum] = mapped_column(
        Enum(EstadoSugerenciaEnum, name="estadosugerenciaenum"),
        default=EstadoSugerenciaEnum.PENDIENTE, nullable=False, index=True,
    )
    revisor_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    motivo: Mapped[str | None] = mapped_column(String(500))  # por qué se rechazó
    publicacion_id: Mapped[int | None] = mapped_column(ForeignKey("publicaciones.id"))
    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    revisada_en: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
