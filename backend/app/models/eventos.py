"""
Modelo EventoCalendario — paros, asuetos, exámenes, eventos culturales, etc.
Soporta alcance general, por comisión o por cursada específica.
"""
import enum
from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TipoEventoEnum(str, enum.Enum):
    paro = "paro"
    asueto = "asueto"
    evento_cultural = "evento_cultural"
    fecha_examen = "fecha_examen"
    otro = "otro"


class AlcanceEventoEnum(str, enum.Enum):
    general = "general"                   # afecta a toda la institución
    comision = "comision"                 # solo una comisión
    materia_especifica = "materia_especifica"  # solo una cursada


class EventoCalendario(Base):
    """
    Registro permanente de eventos académicos.
    Los campos comision_id y cursada_id son opcionales según el alcance.
    """
    __tablename__ = "eventos_calendario"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    titulo: Mapped[str] = mapped_column(String(255), nullable=False)
    tipo: Mapped[TipoEventoEnum] = mapped_column(Enum(TipoEventoEnum), nullable=False, index=True)
    # Fuente del evento: "rectorado", "docente", "sistema", etc.
    origen: Mapped[str | None] = mapped_column(String(100))
    motivo: Mapped[str | None] = mapped_column(Text)

    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fecha_fin: Mapped[date] = mapped_column(Date, nullable=False)
    hora_inicio: Mapped[time | None] = mapped_column(Time)
    hora_fin: Mapped[time | None] = mapped_column(Time)

    alcance: Mapped[AlcanceEventoEnum] = mapped_column(
        Enum(AlcanceEventoEnum), default=AlcanceEventoEnum.general, nullable=False, index=True
    )

    # Opcionales según alcance
    comision_id: Mapped[int | None] = mapped_column(ForeignKey("comisiones.id"), index=True)
    cursada_id: Mapped[int | None] = mapped_column(ForeignKey("cursadas.id"), index=True)

    # Quién cargó el evento
    cargado_por: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), nullable=False)

    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relaciones
    comision: Mapped["Comision | None"] = relationship("Comision", foreign_keys=[comision_id])
    cursada: Mapped["Cursada | None"] = relationship("Cursada", foreign_keys=[cursada_id])
    autor: Mapped["Usuario"] = relationship("Usuario", foreign_keys=[cargado_por])

    def __repr__(self) -> str:
        return f"<EventoCalendario '{self.titulo}' {self.fecha_inicio} alcance={self.alcance}>"
